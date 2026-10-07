import { useId, useState, type ReactNode } from "react"
import { cn } from "../lib"
import type { Filters, Metric, Mode } from "../types"

/** Periods count back from the newest invoice in the data, not from today. */
export const PERIODS = [
  { days: null, label: "All time" },
  { days: 30, label: "Last 30 days" },
  { days: 90, label: "Last 90 days" },
  { days: 180, label: "Last 180 days" },
  { days: 365, label: "Last 365 days" },
]

const MODES: { id: Mode; label: string }[] = [
  { id: "default", label: "Default" },
  { id: "bridge", label: "Bridge" },
  { id: "community", label: "Community" },
]

const METRICS: { id: Metric; label: string }[] = [
  { id: "lift", label: "Lift" },
  { id: "coOrders", label: "Bought together" },
]

const box = "h-8 rounded-lg border border-line bg-surface-raised text-[13px]"
const caption = "text-[12px] font-medium text-ink-muted"

interface ToolbarProps {
  filters: Filters
  /** Every customer segment in the data. */
  segments: string[]
  mode: Mode
  metric: Metric
  /** Whether product types with no pair are drawn. */
  unpaired: boolean
  onFilters: (filters: Filters) => void
  onMode: (mode: Mode) => void
  onMetric: (metric: Metric) => void
  onUnpaired: (unpaired: boolean) => void
}

/**
 * The graph's settings behind one button: which period and customer segment it covers, and how it is drawn.
 * The button opens and collapses the panel, which drops below it; the panel's × and Escape close it too.
 */
export function Toolbar({ filters, segments, mode, metric, unpaired, onFilters, onMode, onMetric, onUnpaired }: ToolbarProps) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <div className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen(!open)}
        className={cn(box, "cursor-pointer px-3 font-medium transition-colors", open ? "text-ink" : "text-ink-muted hover:text-ink")}
      >
        Settings <span aria-hidden>{open ? "▴" : "▾"}</span>
      </button>
      {open && (
        <section
          id={id}
          aria-label="Graph settings"
          onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
          className="absolute top-full right-0 z-10 mt-2 flex w-64 flex-col gap-3 rounded-xl border border-line bg-surface-raised p-4 text-[13px] shadow-pop"
        >
          <header className="flex items-center justify-between">
            <h2 className="font-semibold">Settings</h2>
            <button type="button" aria-label="Close settings" onClick={() => setOpen(false)} className="cursor-pointer px-1 text-[16px] leading-none text-ink-muted hover:text-ink">
              ×
            </button>
          </header>
          <label className="flex flex-col gap-1">
            <span className={caption}>Time range</span>
            <select
              value={filters.days ?? ""}
              onChange={(e) => onFilters({ ...filters, days: Number(e.target.value) || null })}
              className={cn(box, "cursor-pointer px-2")}
            >
              {PERIODS.map((p) => (
                <option key={p.label} value={p.days ?? ""}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className={caption}>Customer segment</span>
            <select
              value={filters.segment ?? ""}
              onChange={(e) => onFilters({ ...filters, segment: e.target.value || null })}
              className={cn(box, "cursor-pointer px-2")}
            >
              <option value="">All customers</option>
              {segments.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <Segmented label="View" options={MODES} value={mode} onChange={onMode} />
          <Segmented label="Line width" options={METRICS} value={metric} onChange={onMetric} />
          <label className="flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={unpaired} onChange={(e) => onUnpaired(e.target.checked)} className="size-4 accent-action" />
            Show product types with no pair
          </label>
        </section>
      )}
    </div>
  )
}

interface SegmentedProps<T extends string> {
  label: ReactNode
  options: { id: T; label: string }[]
  value: T
  onChange: (value: T) => void
}

/** One choice out of a few, side by side. Native radios, so the arrow keys move between them. */
function Segmented<T extends string>({ label, options, value, onChange }: SegmentedProps<T>) {
  const name = useId()
  return (
    <fieldset>
      <legend className={cn(caption, "mb-1")}>{label}</legend>
      <div className={cn(box, "flex overflow-hidden has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-focus")}>
        {options.map((o) => (
          <label
            key={o.id}
            className="flex flex-1 cursor-pointer items-center justify-center px-2 whitespace-nowrap text-ink-muted transition-colors hover:text-ink has-checked:bg-action has-checked:font-semibold has-checked:text-on-action"
          >
            <input type="radio" name={name} checked={value === o.id} onChange={() => onChange(o.id)} className="sr-only" />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
