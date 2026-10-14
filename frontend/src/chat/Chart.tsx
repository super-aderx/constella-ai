import { callText, fmt } from "../lib"
import type { Chart as ChartSpec, ToolCall } from "../types"

/**
 * A chart the scientist asked for, drawn from one tool result in the answer's ledger. Every value
 * on it is a value the tool returned: the spec only says which result, which field and which form.
 */

type Row = Record<string, unknown>

/** The six categorical colours of a pie, in fixed order. Checked for colour-blind separation on the panel's white. */
const SLICES = ["#2f6bd0", "#008c7a", "#c62f3a", "#7b4fc6", "#56841c", "#c43c84"]
/** One hue, light to dark, in five steps: how strong a heat map's cell is. */
const STEPS = [14, 32, 52, 74, 100].map((share) => `color-mix(in srgb, var(--comm-1) ${share}%, var(--surface-raised))`)

const labelOf = (row: Row, label: string) => (label === "pair" ? `${row.a} + ${row.b}` : String(row[label]))
/** Counts and money as whole numbers; ratios such as lift keep their decimals. */
const written = (value: number) => (Number.isInteger(value) || Math.abs(value) >= 100 ? fmt.int(value) : value.toFixed(2))

interface ChartProps {
  chart: ChartSpec
  ledger: ToolCall[]
}

export function Chart({ chart, ledger }: ChartProps) {
  const source = ledger.find((entry) => entry.id === chart.source)
  const rows = (source?.result ?? []) as Row[]
  const data = rows.map((row) => ({ row, label: labelOf(row, chart.label), value: Number(row[chart.value]) }))
  if (data.length === 0) return null
  return (
    <figure className="rounded-xl bg-surface px-3 py-3">
      <figcaption className="mb-2 text-[12px] font-semibold">{chart.title}</figcaption>
      {chart.type === "bar" && <Bars data={data} />}
      {chart.type === "pie" && <Pie data={data} />}
      {chart.type === "heatmap" && <HeatMap rows={rows} value={chart.value} />}
      {/* Where the data is from: the tool call, as it stands in the ledger below. */}
      {source && (
        <p className="mt-2 border-t border-line pt-2 text-[11px] text-ink-muted">
          Data: <span className="font-medium">{chart.value}</span> from <b className="text-ink">{source.id}</b>{" "}
          <code className="font-mono break-words">{callText(source.tool, source.args)}</code>
        </p>
      )}
    </figure>
  )
}

interface Datum {
  label: string
  value: number
}

/** Ranked bars, one hue: the name, the bar from zero, and its value at the end. */
function Bars({ data }: { data: Datum[] }) {
  const max = Math.max(...data.map((d) => d.value), 0) || 1
  return (
    <ol className="grid grid-cols-[minmax(0,auto)_minmax(4rem,1fr)_auto] items-center gap-x-2 gap-y-1 text-[12px]">
      {data.map((d) => (
        <li key={d.label} className="contents" title={`${d.label}: ${written(d.value)}`}>
          <span className="truncate">{d.label}</span>
          <span className="h-3">
            <span className="block h-full min-w-[2px] rounded-r-[4px]" style={{ width: `${(Math.max(d.value, 0) / max) * 100}%`, background: "var(--comm-1)" }} />
          </span>
          <span className="text-right text-ink-muted tabular-nums">{written(d.value)}</span>
        </li>
      ))}
    </ol>
  )
}

/** The parts of one whole. The legend carries each part's name, value and share, so colour is never the only key. */
function Pie({ data }: { data: Datum[] }) {
  const total = data.reduce((sum, d) => sum + d.value, 0) || 1
  // Each slice is an arc of a thick circle, starting where the one before ended.
  const R = 16
  const round = 2 * Math.PI * R
  const starts = data.map((_, i) => data.slice(0, i).reduce((sum, d) => sum + d.value, 0) / total)
  return (
    <div className="flex items-center gap-4">
      <svg viewBox="0 0 64 64" role="img" aria-label="Pie chart" className="size-24 shrink-0 -rotate-90">
        {data.map((d, i) => (
          <circle
            key={d.label}
            cx={32}
            cy={32}
            r={R}
            fill="none"
            stroke={SLICES[i % SLICES.length]}
            strokeWidth={R * 2 - 2}
            // A 1-unit gap of surface between slices.
            strokeDasharray={`${Math.max((d.value / total) * round - 1, 0)} ${round}`}
            strokeDashoffset={-starts[i] * round}
          >
            <title>{`${d.label}: ${written(d.value)}`}</title>
          </circle>
        ))}
      </svg>
      <ul className="flex min-w-0 flex-col gap-1 text-[12px]">
        {data.map((d, i) => (
          <li key={d.label} className="flex items-baseline gap-1.5">
            <span className="size-2.5 shrink-0 translate-y-px rounded-[2px]" style={{ background: SLICES[i % SLICES.length] }} />
            <span className="truncate">{d.label}</span>
            <span className="shrink-0 text-ink-muted tabular-nums">
              {written(d.value)} · {Math.round((d.value / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Pairs as a grid: each product type on both axes, a cell shaded by the pair's value, empty where there is no pair. */
function HeatMap({ rows, value }: { rows: Row[]; value: string }) {
  const cells = new Map(rows.flatMap((r) => [`${r.a}|${r.b}`, `${r.b}|${r.a}`].map((key) => [key, Number(r[value])])))
  // The types with the most pairs first, so the busy corner sits top-left.
  const count = new Map<string, number>()
  for (const r of rows) for (const name of [String(r.a), String(r.b)]) count.set(name, (count.get(name) ?? 0) + 1)
  const names = [...count.keys()].sort((x, y) => count.get(y)! - count.get(x)! || x.localeCompare(y))
  const values = [...cells.values()]
  const low = Math.min(...values)
  const span = Math.max(...values) - low || 1
  const step = (v: number) => STEPS[Math.min(STEPS.length - 1, Math.floor(((v - low) / span) * STEPS.length))]
  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-[2px] text-[11px]">
        <thead>
          <tr>
            <td />
            {names.map((name) => (
              <th key={name} scope="col" className="h-16 w-5 align-bottom font-normal text-ink-muted">
                <span className="[writing-mode:vertical-rl]">{name}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {names.map((row) => (
            <tr key={row}>
              <th scope="row" className="pr-1 text-right font-normal whitespace-nowrap text-ink-muted">
                {row}
              </th>
              {names.map((column) => {
                const v = cells.get(`${row}|${column}`)
                return v == null ? (
                  <td key={column} className="size-5 rounded-[3px] bg-surface-raised" />
                ) : (
                  <td key={column} className="size-5 rounded-[3px]" style={{ background: step(v) }} title={`${row} + ${column}: ${written(v)}`} />
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 flex items-center gap-1 text-[11px] text-ink-muted tabular-nums">
        {written(low)}
        {STEPS.map((color) => (
          <span key={color} className="h-2 w-4 rounded-[2px]" style={{ background: color }} />
        ))}
        {written(low + span)}
      </p>
    </div>
  )
}
