import { useId, type KeyboardEvent, type ReactNode } from "react"
import { cn } from "./lib"

export type Tab = "chat" | "campaigns" | "brief"

const TABS: { tab: Tab; label: string }[] = [
  { tab: "chat", label: "Chat" },
  { tab: "campaigns", label: "Campaigns" },
  { tab: "brief", label: "Brief" },
]

/**
 * The pages of the panel beside the graph. Every page stays mounted and the others are only
 * hidden, so a chat answer still streaming, or a question half typed, is there on coming back.
 * The arrow keys move between tabs, as in any tab list.
 */
export function Tabs({ tab, onTab, panels }: { tab: Tab; onTab: (tab: Tab) => void; panels: Record<Tab, ReactNode> }) {
  const id = useId()
  const tabId = (t: Tab) => `${id}-${t}-tab`
  const panelId = (t: Tab) => `${id}-${t}-panel`

  const onKeyDown = (e: KeyboardEvent) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0
    if (!step) return
    e.preventDefault()
    const at = TABS.findIndex((t) => t.tab === tab)
    const next = TABS[(at + step + TABS.length) % TABS.length].tab
    onTab(next)
    document.getElementById(tabId(next))?.focus()
  }

  return (
    <div className="flex min-h-0 flex-col">
      <div role="tablist" aria-label="Panel" onKeyDown={onKeyDown} className="mb-3 flex shrink-0 gap-1 self-start rounded-xl bg-field p-1">
        {TABS.map((t) => (
          <button
            key={t.tab}
            id={tabId(t.tab)}
            type="button"
            role="tab"
            aria-selected={t.tab === tab}
            aria-controls={panelId(t.tab)}
            tabIndex={t.tab === tab ? 0 : -1}
            onClick={() => onTab(t.tab)}
            className={cn("h-8 cursor-pointer rounded-lg px-3 text-[13px] font-medium transition-colors", t.tab === tab ? "bg-surface-raised text-ink shadow-pop" : "text-ink-muted hover:text-ink")}
          >
            {t.label}
          </button>
        ))}
      </div>
      {TABS.map((t) => (
        <div key={t.tab} id={panelId(t.tab)} role="tabpanel" aria-labelledby={tabId(t.tab)} hidden={t.tab !== tab} className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)]">
          {panels[t.tab]}
        </div>
      ))}
    </div>
  )
}
