import { cn } from "../lib"
import type { Filters, Mode } from "../types"

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

const box = "h-8 rounded-lg border border-line bg-surface-raised text-[13px]"

interface ToolbarProps {
  filters: Filters
  /** Every customer segment in the data. */
  segments: string[]
  mode: Mode
  onFilters: (filters: Filters) => void
  onMode: (mode: Mode) => void
}

/** The graph's controls: which period and customer segment it covers, and how it is drawn. */
export function Toolbar({ filters, segments, mode, onFilters, onMode }: ToolbarProps) {
  return (
    <div className="flex flex-wrap justify-end gap-2">
      <select
        aria-label="Time range"
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
      <select
        aria-label="Customer segment"
        value={filters.segment ?? ""}
        onChange={(e) => onFilters({ ...filters, segment: e.target.value || null })}
        className={cn(box, "cursor-pointer px-2")}
      >
        <option value="">All customers</option>
        {segments.map((s) => (
          <option key={s}>{s}</option>
        ))}
      </select>
      <div role="radiogroup" aria-label="View" className={cn(box, "flex overflow-hidden")}>
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            role="radio"
            aria-checked={mode === m.id}
            onClick={() => onMode(m.id)}
            className={cn("cursor-pointer px-3 transition-colors", mode === m.id ? "bg-action font-semibold text-on-action" : "text-ink-muted hover:text-ink")}
          >
            {m.label}
          </button>
        ))}
      </div>
    </div>
  )
}
