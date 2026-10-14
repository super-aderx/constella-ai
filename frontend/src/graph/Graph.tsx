import { useLayoutEffect, useMemo, useRef, useState, type PointerEvent, type ReactNode } from "react"
import { fmt, pairKey, partnersOf } from "../lib"
import type { Item, Metric, Mode, Network, Pair, PairRef } from "../types"
import { forceLayout, type Positions } from "./layout"

/** A product type in no community is drawn neutral. */
export const communityColor = (community: number | null) => (community == null ? "var(--ink-faint)" : `var(--comm-${(community % 8) + 1})`)

/** What the graph highlights: these items turn peach, these pairs turn peach, everything else dims. */
export interface Lit {
  items: string[]
  pairs: PairRef[]
}

interface GraphProps {
  network: Network
  lit: Lit
  /**
   * The network to lay out instead of `network`: the two sides of a comparison share one, so a
   * product type sits in the same place on both graphs.
   */
  layout?: Network
  mode: Mode
  metric: Metric
  /** Shown beside the zoom buttons. */
  toolbar?: ReactNode
  /** A product type was clicked, or `null` for the empty canvas. */
  onSelect: (item: string | null) => void
  /** Laid over the canvas. */
  children?: ReactNode
}

const PAD = { x: 72, top: 84, bottom: 84 }
const HOME = { x: 0, y: 0, k: 1 }
const ZOOM = { min: 0.5, max: 4, step: 1.3 }
const control = "h-8 min-w-8 cursor-pointer px-2 text-ink-muted transition-colors hover:text-ink disabled:pointer-events-none disabled:opacity-40"

/**
 * The product type network on a white panel, drawn to the size of its container.
 * Star size = orders, line width = lift or the baskets with both (`metric`). In the lift view, a pair
 * bought together less often than chance predicts is dashed and blue. Scroll or use the buttons to zoom, drag the canvas to pan and
 * a product type to move it. Zooming spreads the product types apart; stars and names keep a readable size.
 * Hovering a product type lights its pairs; hovering a pair shows its figures; a click selects a product type.
 */
export function Graph({ network, lit, layout = network, mode, metric, toolbar, onSelect, children }: GraphProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [{ width, height }, setSize] = useState({ width: 800, height: 600 })
  const [view, setView] = useState(HOME)
  /** Product types dragged away from where the layout put them. */
  const [moved, setMoved] = useState<Positions>({})
  /** An item's name or a pair's key. */
  const [hover, setHover] = useState<string | null>(null)
  /** The gesture in progress: on a product type or on the canvas, and whether it has become a drag. */
  const drag = useRef<{ item: string | null; x: number; y: number; moved: boolean }>(null)

  /** Zooms by `factor`, keeping the point (cx, cy) of the canvas where it is. */
  const zoom = (factor: number, cx = width / 2, cy = height / 2) =>
    setView((v) => {
      const k = Math.min(ZOOM.max, Math.max(ZOOM.min, v.k * factor))
      return { k, x: cx - (cx - v.x) * (k / v.k), y: cy - (cy - v.y) * (k / v.k) }
    })

  useLayoutEffect(() => {
    const el = ref.current!
    const observer = new ResizeObserver(([entry]) => setSize(entry.contentRect))
    observer.observe(el)
    // Not React's onWheel: that one is passive, and the page would scroll or pinch-zoom too.
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const box = el.getBoundingClientRect()
      zoom(Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.002)), e.clientX - box.left, e.clientY - box.top)
    }
    el.addEventListener("wheel", onWheel, { passive: false })
    return () => {
      observer.disconnect()
      el.removeEventListener("wheel", onWheel)
    }
  }, [])

  const positions = useMemo(() => forceLayout(layout.items, layout.pairs), [layout])
  const inner = { w: width - PAD.x * 2, h: height - PAD.top - PAD.bottom }
  const at = (name: string) => {
    const [x, y] = moved[name] ?? positions[name]
    return [view.x + (PAD.x + x * inner.w) * view.k, view.y + (PAD.top + y * inner.h) * view.k]
  }

  const onPointerDown = (e: PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return
    const item = (e.target as Element).closest("[data-item]")?.getAttribute("data-item") ?? null
    drag.current = { item, x: e.clientX, y: e.clientY, moved: false }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: PointerEvent) => {
    const d = drag.current
    if (!d) return
    const dx = e.clientX - d.x
    const dy = e.clientY - d.y
    // A few px of slack, so a click with a shaky hand is still a click.
    if (!d.moved && Math.hypot(dx, dy) < 4) return
    Object.assign(d, { x: e.clientX, y: e.clientY, moved: true })
    const item = d.item
    if (item) {
      setMoved((m) => {
        const [x, y] = m[item] ?? positions[item]
        return { ...m, [item]: [x + dx / (view.k * inner.w), y + dy / (view.k * inner.h)] }
      })
    } else {
      setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy }))
    }
  }
  const onPointerUp = () => {
    const d = drag.current
    drag.current = null
    if (d && !d.moved) onSelect(d.item)
  }

  const maxOrders = Math.max(...network.items.map((i) => i.orders))
  const radius = (item: Item) => (5 + 11 * Math.sqrt(item.orders / maxOrders)) * Math.sqrt(view.k)
  // Baskets are skewed toward the best sellers, so their widths grow with the square root.
  const weight = (p: Pair) => (metric === "lift" ? p.lift : Math.sqrt(p.coOrders))
  const weights = network.pairs.map(weight)
  const minWeight = Math.min(...weights)
  const weightSpan = Math.max(...weights) - minWeight || 1

  const stars = new Set(lit.items)
  const litPairs = new Set(lit.pairs.map((p) => pairKey(p.a, p.b)))
  // A hovered product type lights its own neighbourhood; otherwise the highlight does.
  const hoverItem = hover != null && hover in positions ? hover : null
  const awake = hoverItem
    ? new Set([hoverItem, ...partnersOf(network.pairs, hoverItem).map((p) => p.name)])
    : new Set([...lit.items, ...lit.pairs.flatMap((p) => [p.a, p.b])])
  const focused = awake.size > 0
  const hoverPair = network.pairs.find((p) => pairKey(p.a, p.b) === hover)

  const fill = (item: Item) =>
    mode === "community" ? communityColor(item.community) : mode === "bridge" && !item.bridge ? "var(--ink-faint)" : "var(--action)"

  // Community view: a soft disc behind each community, centred on its product types, reaching the farthest one.
  const discs = (mode === "community" ? network.communities : []).map((_, c) => {
    const points = network.items.filter((i) => i.community === c).map((i) => at(i.name))
    const cx = points.reduce((sum, p) => sum + p[0], 0) / points.length
    const cy = points.reduce((sum, p) => sum + p[1], 0) / points.length
    return { cx, cy, r: Math.max(...points.map((p) => Math.hypot(p[0] - cx, p[1] - cy))) + 34 * Math.sqrt(view.k) }
  })

  return (
    <div
      ref={ref}
      className="relative min-h-0 overflow-hidden rounded-2xl bg-surface-raised"
    >
      <svg
        width={width}
        height={height}
        role="group"
        aria-label="Product type network"
        className="absolute inset-0 cursor-grab touch-none select-none active:cursor-grabbing"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => (drag.current = null)}
      >
        <defs>
          {/* The dot grid moves with the view, so panning and zooming read as moving a surface */}
          <pattern id="dots" width={28} height={28} patternUnits="userSpaceOnUse" patternTransform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
            <circle cx={1} cy={1} r={1} fill="var(--ink)" opacity={0.1} />
          </pattern>
        </defs>

        <g aria-hidden className="pointer-events-none">
          <rect width={width} height={height} fill="url(#dots)" />
          {discs.map((d, c) => (
            <circle key={c} cx={d.cx} cy={d.cy} r={d.r} fill={communityColor(c)} opacity={0.07} />
          ))}
        </g>

        <g aria-hidden>
          {network.pairs.map((p, i) => {
            const key = pairKey(p.a, p.b)
            const [x1, y1] = at(p.a)
            const [x2, y2] = at(p.b)
            const on = litPairs.has(key)
            const near = p.a === hoverItem || p.b === hoverItem
            const below = metric === "lift" && p.lift < 1
            return (
              <g key={key} onMouseEnter={() => setHover(key)} onMouseLeave={() => setHover(null)}>
                <line
                  {...{ x1, y1, x2, y2 }}
                  // A solid line draws itself in; a dashed one keeps its dashes, so it is there from the start.
                  {...(below ? { strokeDasharray: "5 5" } : { pathLength: 1, strokeDasharray: 1, strokeLinecap: "round" })}
                  strokeWidth={1 + 3 * ((weight(p) - minWeight) / weightSpan) + (on ? 1 : 0)}
                  stroke={on ? "var(--star)" : near || hover === key ? "var(--edge-strong)" : below ? "var(--edge-below)" : "var(--edge)"}
                  opacity={focused && !(hoverItem ? near : on) && hover !== key ? 0.3 : 1}
                  className="animate-edge-draw transition-[stroke,opacity] duration-200"
                  // The pairs draw in one after another, all within 2 s however many there are.
                  style={{ animationDelay: `${500 + i * Math.min(14, 2000 / network.pairs.length)}ms` }}
                />
                {/* A wide invisible line: the pair's hover target */}
                <line {...{ x1, y1, x2, y2 }} stroke="transparent" strokeWidth={14} />
              </g>
            )
          })}
        </g>

        {network.items.map((item, i) => {
          const [x, y] = at(item.name)
          const r = radius(item)
          const star = stars.has(item.name)
          // Every name shows; while something is highlighted, only the names it involves.
          const labelled = hover === item.name || !focused || awake.has(item.name)
          return (
            <g
              key={item.name}
              data-item={item.name}
              transform={`translate(${x} ${y})`}
              role="button"
              tabIndex={0}
              aria-label={item.name}
              aria-pressed={star}
              opacity={focused && !awake.has(item.name) ? 0.3 : 1}
              className="cursor-pointer transition-opacity duration-200"
              onMouseEnter={() => setHover(item.name)}
              onMouseLeave={() => setHover(null)}
              onKeyDown={(e) => {
                if (e.key !== "Enter" && e.key !== " ") return
                // Space would scroll the page.
                e.preventDefault()
                onSelect(item.name)
              }}
            >
              <g className="origin-center animate-star-in [transform-box:fill-box]" style={{ animationDelay: `${i * 18}ms` }}>
                {star && <circle r={r + 7} fill="var(--star)" opacity={0.22} />}
                <circle r={r} fill={star ? "var(--star)" : fill(item)} opacity={mode === "bridge" && !item.bridge && !star ? 0.5 : 1} />
                {hover === item.name && <circle r={r + 4} fill="none" stroke="var(--ink)" strokeOpacity={0.6} strokeWidth={1.5} />}
              </g>
              {labelled && (
                <text y={r + 16} textAnchor="middle" className={`fill-ink text-[12px] ${star ? "font-semibold" : "font-medium"}`}>
                  {item.name}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {hoverPair && (
        <p
          className="pointer-events-none absolute -translate-x-1/2 -translate-y-[calc(100%+10px)] rounded-lg bg-action px-2.5 py-1.5 text-[12px] whitespace-nowrap text-on-action shadow-pop"
          style={{ left: (at(hoverPair.a)[0] + at(hoverPair.b)[0]) / 2, top: (at(hoverPair.a)[1] + at(hoverPair.b)[1]) / 2 }}
        >
          <span className="font-semibold">
            {hoverPair.a} + {hoverPair.b}
          </span>
          <span className="ml-2 tabular-nums opacity-70">
            {fmt.int(hoverPair.coOrders)} baskets · {fmt.lift(hoverPair.lift)} lift
          </span>
        </p>
      )}

      <div className="absolute top-4 right-4 flex items-start gap-2">
      <div className="flex items-center rounded-lg border border-line bg-surface-raised text-[15px]">
        <button type="button" aria-label="Zoom out" disabled={view.k <= ZOOM.min} onClick={() => zoom(1 / ZOOM.step)} className={control}>
          −
        </button>
        <span className="w-10 text-center text-[12px] text-ink-muted tabular-nums">{Math.round(view.k * 100)}%</span>
        <button type="button" aria-label="Zoom in" disabled={view.k >= ZOOM.max} onClick={() => zoom(ZOOM.step)} className={control}>
          +
        </button>
        <button
          type="button"
          onClick={() => {
            setView(HOME)
            setMoved({})
          }}
          className={`${control} border-l border-line px-3 text-[12px] font-medium`}
        >
          Reset
        </button>
      </div>
        {toolbar}
      </div>

      <ul className="pointer-events-none absolute bottom-4 left-4 flex max-w-[calc(100%-19rem)] flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-muted max-sm:hidden">
        {mode === "community" &&
          network.communities.map((label, c) => (
            <li key={label} className="inline-flex items-center gap-1.5">
              <span className="size-2.5 rounded-full" style={{ background: communityColor(c) }} />
              {label}
            </li>
          ))}
        {mode === "bridge" && (
          <li className="inline-flex items-center gap-1.5">
            <span className="size-2.5 rounded-full bg-action" />
            Bridge: connects the most other product types
          </li>
        )}
        {metric === "lift" && network.pairs.some((p) => p.lift < 1) && (
          <li className="inline-flex items-center gap-1.5">
            <span className="w-4 border-t-2 border-dashed border-(--edge-below)" />
            Bought together often, but less than chance predicts
          </li>
        )}
        <li className="text-ink-faint">Star size: orders · Line width: {metric === "lift" ? "lift" : "baskets with both"}</li>
      </ul>
      {children}
    </div>
  )
}
