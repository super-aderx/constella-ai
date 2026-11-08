import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react"
import { cn } from "../lib"
import type { SavedCampaign } from "../types"
import { today } from "./draft"
import { fetchCampaignTrend, shortDate, summarize, TREND_METRICS, type TrendMetric, type TrendPoint } from "./trend"

/**
 * The local date, moved on at midnight. The panel stays mounted when the user looks elsewhere, so a
 * running campaign left open overnight would otherwise keep ending its chart on yesterday.
 */
function useToday() {
  const [day, setDay] = useState(() => today())
  useEffect(() => {
    const now = new Date()
    // A second past midnight, so a timer that fires a touch early still lands on the new day.
    const next = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 1)
    const timer = setTimeout(() => setDay(today()), next.getTime() - now.getTime())
    return () => clearTimeout(timer)
  }, [day])
  return day
}

/**
 * How a live or finished campaign has done, day by day, in one metric at a time. Nothing is shown
 * for a campaign that never went live. The data is sample data until the trend API exists, and
 * the heading says so.
 */
export function CampaignTrend({ campaign }: { campaign: SavedCampaign }) {
  const [points, setPoints] = useState<TrendPoint[] | null>(null)
  const [metric, setMetric] = useState<TrendMetric>("revenue")
  const id = useId()
  const { id: campaignId, status, launched_at, approved_at, ended_at, cancelled_at, starts_on, ends_on } = campaign
  const { starts_on: pilotStart, ends_on: pilotEnd, auto_start: autoStart } = campaign.pilot ?? {}
  const day = useToday()

  // Only what decides the range: a change elsewhere in the campaign keeps the chart as it is. The
  // fetch reads today itself; `day` is here so a running campaign gains its new day at midnight.
  useEffect(() => {
    let live = true
    setPoints(null)
    fetchCampaignTrend(campaign).then(
      (loaded) => live && setPoints(loaded),
      // No trend is better than a broken detail page; the real API will bring its own error state.
      () => live && setPoints(null),
    )
    return () => {
      live = false
    }
  }, [campaignId, status, launched_at, approved_at, ended_at, cancelled_at, starts_on, ends_on, pilotStart, pilotEnd, autoStart, day])

  if (!points || points.length === 0) return null
  const shown = TREND_METRICS.find((m) => m.key === metric)!
  const tabId = (key: TrendMetric) => `${id}-${key}-tab`

  const onKeyDown = (e: KeyboardEvent) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0
    if (!step) return
    e.preventDefault()
    const at = TREND_METRICS.findIndex((m) => m.key === metric)
    const next = TREND_METRICS[(at + step + TREND_METRICS.length) % TREND_METRICS.length].key
    setMetric(next)
    document.getElementById(tabId(next))?.focus()
  }

  return (
    <section className="mt-4 border-t border-line pt-4">
      <div className="flex items-center gap-2">
        <h4 className="text-[14px] font-semibold">Daily trend</h4>
        <span className="rounded-full bg-field px-2 py-px text-[12px] text-ink-muted">Sample data</span>
      </div>
      <div role="tablist" aria-label="Metric" onKeyDown={onKeyDown} className="mt-2 flex flex-wrap gap-1">
        {TREND_METRICS.map((m) => (
          <button
            key={m.key}
            id={tabId(m.key)}
            type="button"
            role="tab"
            aria-selected={m.key === metric}
            tabIndex={m.key === metric ? 0 : -1}
            onClick={() => setMetric(m.key)}
            className={cn("h-7 cursor-pointer rounded-lg px-2.5 text-[12px] font-medium transition-colors", m.key === metric ? "bg-field text-ink" : "text-ink-muted hover:text-ink")}
          >
            {m.label}
          </button>
        ))}
      </div>
      <p className="mt-2 text-[13px] text-ink-muted">
        {shown.label}
        {shown.summary === "mean" ? " (average)" : ""} · <span className="text-[16px] font-semibold text-ink tabular-nums">{shown.format(summarize(points, metric))}</span>
      </p>
      <LineChart points={points} metric={metric} />
    </section>
  )
}

const HEIGHT = 160
/** Room for the y labels on the left and the x labels below. */
const PAD = { left: 52, right: 12, top: 10, bottom: 22 }
const MAX_X_LABELS = 6

/** The smallest of 1, 2, 2.5, 3, 4, 5 × 10ⁿ at or above `v`: a step that reads well on an axis without leaving half of it empty. */
function niceStep(v: number) {
  const power = 10 ** Math.floor(Math.log10(v))
  return ([1, 2, 2.5, 3, 4, 5, 10].find((m) => m * power >= v) ?? 10) * power
}

/** Up to six indexes spread evenly, always the first and the last; fewer when the chart is narrow. */
function labelIndexes(count: number, plotW: number) {
  // A label such as "Sep 17" needs about 64px: a narrow panel gets fewer of them.
  const most = Math.max(2, Math.min(MAX_X_LABELS, Math.floor(plotW / 64) + 1))
  if (count <= most) return [...Array(count).keys()]
  return [...new Set([...Array(most).keys()].map((i) => Math.round((i * (count - 1)) / (most - 1))))]
}

/** One metric over the days: a line with a faint area under it, or a dot when there is one day. */
function LineChart({ points, metric }: { points: TrendPoint[]; metric: TrendMetric }) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [hover, setHover] = useState<number | null>(null)
  const { label, format, summary } = TREND_METRICS.find((m) => m.key === metric)!

  useLayoutEffect(() => {
    const el = ref.current!
    // Measured now as well, so the chart is there on the first paint rather than a frame later.
    setWidth(el.clientWidth)
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const values = points.map((p) => p[metric])
  // Three steps from zero to at least the highest day; all-zero days still get a scale.
  const nice = niceStep((Math.max(...values) || 1) / 3)
  // Counts and money are labelled in whole units: a 0.4 or 2.5 step would print 0, 0, 1, 1 or
  // 0, 3, 5, 8 at evenly spaced heights. Only the averaged rate keeps a fractional step.
  const step = summary === "mean" ? nice : Math.ceil(nice)
  const top = step * 3
  const plotW = Math.max(width - PAD.left - PAD.right, 0)
  const plotH = HEIGHT - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (points.length === 1 ? plotW / 2 : (i / (points.length - 1)) * plotW)
  const y = (v: number) => PAD.top + plotH - (v / top) * plotH
  const line = values.map((v, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(v)}`).join("")
  const area = `${line}L${x(points.length - 1)},${y(0)}L${x(0)},${y(0)}Z`
  const first = shortDate(points[0].date)
  const last = shortDate(points[points.length - 1].date)

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const at = e.clientX - e.currentTarget.getBoundingClientRect().left
    setHover(points.length === 1 ? 0 : Math.min(points.length - 1, Math.max(0, Math.round(((at - PAD.left) / (plotW || 1)) * (points.length - 1)))))
  }

  const tip = hover === null ? null : `${shortDate(points[hover].date)} · ${format(values[hover])}`
  // Keep the hover label inside the chart: anchored by its side, not its middle, near the edges.
  const tipAnchor = hover === null ? "middle" : x(hover) < PAD.left + 60 ? "start" : x(hover) > width - 60 ? "end" : "middle"

  return (
    // The height is held while the width is unknown (a hidden tab), so nothing jumps when it is drawn.
    <div ref={ref} className="mt-1 w-full" style={{ height: HEIGHT }}>
      {/* The hover readout needs a pointer: keyboard and screen-reader users get the same days and
          values as a table, and the drawing is hidden from them so it is not read twice. */}
      <table className="sr-only">
        <caption>{`${label} per day, ${first}${points.length > 1 ? ` to ${last}` : ""}. Sample data.`}</caption>
        <thead>
          <tr>
            <th scope="col">Date</th>
            <th scope="col">{label}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p, i) => (
            <tr key={p.date}>
              <th scope="row">{shortDate(p.date)}</th>
              <td>{format(values[i])}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {width > 0 && (
        <svg
          width={width}
          height={HEIGHT}
          aria-hidden
          onPointerMove={onMove}
          onPointerLeave={() => setHover(null)}
          className="block text-[11px]"
        >
          {[0, 1, 2, 3].map((i) => (
            <g key={i}>
              <line x1={PAD.left} x2={PAD.left + plotW} y1={y(step * i)} y2={y(step * i)} stroke="var(--line)" />
              <text x={PAD.left - 6} y={y(step * i)} textAnchor="end" dominantBaseline="middle" fill="var(--ink-muted)" className="tabular-nums">
                {format(step * i)}
              </text>
            </g>
          ))}
          {labelIndexes(points.length, plotW).map((i) => (
            <text key={i} x={x(i)} y={HEIGHT - 6} textAnchor={points.length === 1 ? "middle" : i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"} fill="var(--ink-muted)">
              {shortDate(points[i].date)}
            </text>
          ))}
          {points.length === 1 ? (
            <circle cx={x(0)} cy={y(values[0])} r={3.5} fill="var(--comm-1)" />
          ) : (
            <>
              <path d={area} fill="var(--comm-1)" fillOpacity={0.12} />
              <path d={line} fill="none" stroke="var(--comm-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            </>
          )}
          {hover !== null && (
            <g pointerEvents="none">
              <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + plotH} stroke="var(--ink-muted)" strokeDasharray="2 3" />
              <circle cx={x(hover)} cy={y(values[hover])} r={4} fill="var(--comm-1)" stroke="var(--surface-raised)" strokeWidth={2} />
              <text x={x(hover)} y={PAD.top - 1} textAnchor={tipAnchor} dominantBaseline="hanging" fill="var(--ink)" className="font-medium tabular-nums" paintOrder="stroke" stroke="var(--surface-raised)" strokeWidth={4}>
                {tip}
              </text>
            </g>
          )}
        </svg>
      )}
    </div>
  )
}
