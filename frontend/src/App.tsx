import { use, useDeferredValue, useMemo, useRef, useState, type CSSProperties } from "react"
import { ask, getNetwork } from "./api"
import { Logo } from "./Brand"
import { Chat } from "./chat/Chat"
import { Graph, type Lit } from "./graph/Graph"
import { ItemCard } from "./graph/ItemCard"
import { PERIODS, Toolbar } from "./graph/Toolbar"
import { cn, pairKey, partnersOf } from "./lib"
import type { Answer, Filters, Metric, Mode, Network, Step, Turn } from "./types"

const same = (a: Filters, b: Filters) => a.days === b.days && a.segment === b.segment

/** A scope in words: "Last 90 days, 忠誠客戶". */
const periodLabel = (days: number | null) => (days ? (PERIODS.find((p) => p.days === days)?.label ?? `Last ${days} days`) : "All time")
const scopeLabel = (scope: Filters) => `${periodLabel(scope.days)}, ${scope.segment ?? "All customers"}`

/**
 * What a graph draws of a network. A product type with no pair is hidden unless asked for, or unless
 * the answer on show names it: the agent knows every type, and what it highlights has to be there.
 */
function visible(network: Network, unpaired: boolean, shown: Answer | null): Network {
  if (unpaired) return network
  const kept = new Set([...network.pairs.flatMap((p) => [p.a, p.b]), ...(shown?.items ?? [])])
  return { ...network, items: network.items.filter((i) => kept.has(i.name)) }
}

/** What a graph highlights: the selected type and its pairs, else what the answer on show names. */
function litFor(network: Network, selected: string | null, shown: Answer | null): Lit {
  return selected
    ? { items: [selected], pairs: partnersOf(network.pairs, selected).map((p) => ({ a: selected, b: p.name })) }
    : { items: shown?.items ?? [], pairs: shown?.pairs ?? [] }
}

/** Two networks as one, to lay out: every type and pair of either, so both graphs can share positions. */
function union(a: Network, b: Network): Network {
  const names = new Set(a.items.map((i) => i.name))
  const keys = new Set(a.pairs.map((p) => pairKey(p.a, p.b)))
  return {
    ...a,
    items: [...a.items, ...b.items.filter((i) => !names.has(i.name))],
    pairs: [...a.pairs, ...b.pairs.filter((p) => !keys.has(pairKey(p.a, p.b)))],
  }
}

/** The chat's width beside the graph, in px: what it starts at, and how far it can be dragged. */
const CHAT = { initial: 432, min: 320, max: 760, key: "chat-width" }

/** The width chosen last time, if the browser kept it. */
function storedWidth() {
  try {
    const stored = Number(localStorage.getItem(CHAT.key))
    return stored >= CHAT.min && stored <= CHAT.max ? stored : CHAT.initial
  } catch {
    return CHAT.initial
  }
}

const IGNORED_KEY = "ignored-types"

/** The product types set aside last time, if the browser kept them. */
function storedIgnored(): string[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(IGNORED_KEY) ?? "[]")
    return Array.isArray(stored) ? stored.filter((type) => typeof type === "string") : []
  } catch {
    return []
  }
}

/**
 * The two features side by side: the network graph and the chat. They are linked both ways:
 * an answer lights up its items and pairs on the graph, and a product type on the graph can be asked about.
 * The graph follows the answer's scope too: it switches to the period or segment an answer is about,
 * and splits in two when an answer compares two scopes.
 */
export default function App() {
  /** The filters chosen: what the toolbar shows and the agent is asked about. */
  const [filters, setFilters] = useState<Filters>({ days: null, segment: null })
  /** The same, readable after an await. */
  const chosen = useRef(filters)
  /** The second scope of a comparison: the graph beside the first. */
  const [compare, setCompare] = useState<Filters | null>(null)
  /** The scopes of the networks on screen. A new scope keeps the old graph, dimmed, until its network arrives. */
  const loaded = useDeferredValue(filters)
  const compared = useDeferredValue(compare)
  const loading = loaded !== filters || compared !== compare
  const [mode, setMode] = useState<Mode>("community")
  const [metric, setMetric] = useState<Metric>("lift")
  /** Whether product types with no pair are drawn. */
  const [unpaired, setUnpaired] = useState(false)
  const network = use(getNetwork(loaded))
  const other = compared ? use(getNetwork(compared)) : null
  const [turns, setTurns] = useState<Turn[]>([])
  /** The product type clicked on a graph. It takes over the highlight from `shown`. */
  const [selected, setSelected] = useState<string | null>(null)
  /** The answer highlighted on the graph. */
  const [shown, setShown] = useState<Answer | null>(null)
  const [chatWidth, setChatWidth] = useState(storedWidth)
  /** The product types the assistant builds no campaign on. The graph draws them all the same. */
  const [ignored, setIgnored] = useState(storedIgnored)
  const ignore = (type: string) => {
    const next = ignored.includes(type) ? ignored.filter((t) => t !== type) : [...ignored, type]
    setIgnored(next)
    try {
      localStorage.setItem(IGNORED_KEY, JSON.stringify(next))
    } catch {
      // Not kept for next time: the choice still applies now.
    }
  }
  // Never so wide that the graph is left with less than the chat's own minimum.
  const resize = (width: number) => {
    const next = Math.round(Math.max(CHAT.min, Math.min(width, CHAT.max, window.innerWidth - CHAT.min)))
    setChatWidth(next)
    try {
      localStorage.setItem(CHAT.key, String(next))
    } catch {
      // Not kept for next time: the width still applies now.
    }
  }
  const drawn = useMemo(() => visible(network, unpaired, shown), [network, unpaired, shown])
  const drawnOther = useMemo(() => other && visible(other, unpaired, shown), [other, unpaired, shown])
  const shared = useMemo(() => (other ? union(network, other) : undefined), [network, other])
  const types = useMemo(() => network.items.map((i) => i.name), [network])

  // Showing an answer also shows its scope: the graph switches to it, and splits for a comparison.
  // The conversation carries on, and the next question is asked about what is now on screen.
  const show = (answer: Answer | null) => {
    setSelected(null)
    setShown(answer)
    const [first, second] = answer?.views ?? []
    if (!first) return
    if (!same(first, chosen.current)) {
      chosen.current = first
      setFilters(first)
    }
    setCompare(second ?? null)
  }

  // A filter chosen by hand: the selected type may not exist under it, and the answers are about
  // the old one. The highlight, the comparison and the conversation are cleared with it.
  const filter = (next: Filters) => {
    chosen.current = next
    setTurns([])
    setSelected(null)
    setShown(null)
    setCompare(null)
    setFilters(next)
  }

  // One question at a time, so only the last turn can be waiting.
  const send = async (question: string) => {
    if (turns.some((t) => !t.answer)) return
    setTurns((t) => [...t, { question }])
    // A failed request is shown as the answer, so the chat never hangs.
    const asked = chosen.current
    const step = (step: Step) => {
      // As below: a step of a run whose conversation was cleared has no turn to go on.
      if (chosen.current !== asked) return
      setTurns((t) => {
        const last = t[t.length - 1]
        return last && !last.answer ? [...t.slice(0, -1), { ...last, steps: [...(last.steps ?? []), step] }] : t
      })
    }
    const answer = await ask(question, asked, ignored, step).catch((error: Error) => ({ text: error.message, items: [], pairs: [] }))
    // The filters changed while it was waiting: the answer is about a network no longer shown.
    if (chosen.current !== asked) return
    setTurns((t) => [...t.slice(0, -1), { question, answer }])
    show(answer)
  }

  const select = (item: string | null) => {
    if (item) setSelected(item === selected ? null : item)
    else {
      setSelected(null)
      setShown(null)
    }
  }

  return (
    <main
      className="grid h-dvh grid-rows-[45dvh_minmax(0,1fr)] gap-3 p-3 lg:grid-cols-[minmax(0,1fr)_var(--chat-width)] lg:grid-rows-1 lg:gap-5 lg:p-5"
      style={{ "--chat-width": `${chatWidth}px` } as CSSProperties}
    >
      <div className={cn("grid min-h-0 gap-3 transition-opacity", drawnOther && "grid-cols-2", loading && "opacity-50")}>
        <Graph
          network={drawn}
          layout={shared}
          lit={litFor(network, selected, shown)}
          mode={mode}
          metric={metric}
          toolbar={
            <Toolbar
              filters={filters}
              segments={network.segments}
              mode={mode}
              metric={metric}
              unpaired={unpaired}
              onFilters={filter}
              onMode={setMode}
              onMetric={setMetric}
              onUnpaired={(next) => {
                // The selected type may be one of those now hidden.
                if (!next) setSelected(null)
                setUnpaired(next)
              }}
            />
          }
          onSelect={select}
        >
          <div className="pointer-events-none absolute top-5 left-5 max-w-[60%]">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <Logo />
              <p className="text-[14px] font-semibold">{scopeLabel(loaded)}</p>
              <p className="text-[12px] text-ink-muted">
                {drawn.items.length} product types · {drawn.pairs.length} pairs bought together {network.minCoOrders}+ times
              </p>
            </div>
          </div>
          {selected && network.items.some((i) => i.name === selected) && <ItemCard network={network} name={selected} onSelect={setSelected} onAsk={send} ignored={ignored.includes(selected)} onIgnore={() => ignore(selected)} />}
        </Graph>
        {other && drawnOther && compared && (
          <Graph
            network={drawnOther}
            layout={shared}
            lit={litFor(other, selected, shown)}
            mode={mode}
            metric={metric}
            toolbar={
              <button type="button" onClick={() => setCompare(null)} className="h-8 cursor-pointer rounded-lg border border-line bg-surface-raised px-3 text-[13px] text-ink-muted hover:text-ink">
                Close comparison
              </button>
            }
            onSelect={select}
          >
            <div className="pointer-events-none absolute top-5 left-5 max-w-[60%]">
              <p className="text-[12px] font-medium text-ink-muted">Compared with</p>
              <p className="text-[14px] font-semibold">{scopeLabel(compared)}</p>
              <p className="text-[12px] text-ink-muted">
                {drawnOther.items.length} product types · {drawnOther.pairs.length} pairs bought together {other.minCoOrders}+ times
              </p>
            </div>
            {/* The same type's card on this side, with this scope's figures. */}
            {selected && other.items.some((i) => i.name === selected) && <ItemCard network={other} name={selected} onSelect={setSelected} onAsk={send} ignored={ignored.includes(selected)} onIgnore={() => ignore(selected)} />}
          </Graph>
        )}
      </div>
      <div className="relative grid min-h-0 grid-rows-[minmax(0,1fr)]">
        {/* Side by side only: the handle sits in the gap between the graph and the chat. Drag it, or use the arrow keys; a double click resets. */}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize the chat"
          aria-valuenow={chatWidth}
          aria-valuemin={CHAT.min}
          aria-valuemax={CHAT.max}
          tabIndex={0}
          title="Drag to resize"
          onPointerDown={(e) => e.currentTarget.setPointerCapture(e.pointerId)}
          // The chat ends at the page's padding, so its width is what lies right of the pointer, less that.
          onPointerMove={(e) => e.currentTarget.hasPointerCapture(e.pointerId) && resize(window.innerWidth - e.clientX - 20)}
          onDoubleClick={() => resize(CHAT.initial)}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") resize(chatWidth + 16)
            if (e.key === "ArrowRight") resize(chatWidth - 16)
          }}
          className="group absolute inset-y-0 -left-5 hidden w-5 cursor-col-resize touch-none justify-center lg:flex"
        >
          <span className="w-0.5 rounded-full bg-transparent transition-colors group-hover:bg-line group-focus-visible:bg-line group-active:bg-ink-faint" />
        </div>
        <Chat
          turns={turns}
          types={types}
          ignored={ignored}
          onIgnore={ignore}
          shown={selected ? null : shown}
          onSend={send}
          onShow={show}
          onReset={() => {
            setTurns([])
            setSelected(null)
            setShown(null)
          }}
        />
      </div>
    </main>
  )
}
