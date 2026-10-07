import { use, useDeferredValue, useMemo, useRef, useState } from "react"
import { ask, getNetwork } from "./api"
import { Logo } from "./Brand"
import { Chat } from "./chat/Chat"
import { Graph, type Lit } from "./graph/Graph"
import { ItemCard } from "./graph/ItemCard"
import { PERIODS, Toolbar } from "./graph/Toolbar"
import { cn, partnersOf } from "./lib"
import type { Answer, Filters, Metric, Mode, Turn } from "./types"

const TITLE = "高雄市 某零售商 產品並買圖"

/**
 * The two features side by side: the network graph and the chat. They are linked both ways:
 * an answer lights up its items and pairs on the graph, and a product type on the graph can be asked about.
 */
export default function App() {
  /** The filters chosen: what the toolbar shows and the agent is asked about. */
  const [filters, setFilters] = useState<Filters>({ days: null, segment: null })
  /** The same, readable after an await. */
  const chosen = useRef(filters)
  /** The filters of the network on screen. A new filter keeps the old graph, dimmed, until its network arrives. */
  const loaded = useDeferredValue(filters)
  const loading = loaded !== filters
  const [mode, setMode] = useState<Mode>("community")
  const [metric, setMetric] = useState<Metric>("lift")
  /** Whether product types with no pair are drawn. */
  const [unpaired, setUnpaired] = useState(false)
  const network = use(getNetwork(loaded))
  const [turns, setTurns] = useState<Turn[]>([])
  /** The product type clicked on the graph. It takes over the highlight from `shown`. */
  const [selected, setSelected] = useState<string | null>(null)
  /** The answer highlighted on the graph. */
  const [shown, setShown] = useState<Answer | null>(null)
  // What the graph draws. A product type with no pair is hidden unless asked for, or unless the answer
  // on show names it: the agent knows every type, and what it highlights has to be there.
  const drawn = useMemo(() => {
    if (unpaired) return network
    const kept = new Set([...network.pairs.flatMap((p) => [p.a, p.b]), ...(shown?.items ?? [])])
    return { ...network, items: network.items.filter((i) => kept.has(i.name)) }
  }, [network, unpaired, shown])

  const show = (answer: Answer | null) => {
    setSelected(null)
    setShown(answer)
  }

  // The selected type may not exist under the new filter, and the answers are about the old one:
  // the highlight and the conversation are cleared with it.
  const filter = (next: Filters) => {
    chosen.current = next
    setTurns([])
    show(null)
    setFilters(next)
  }

  // One question at a time, so only the last turn can be waiting.
  const send = async (question: string) => {
    if (turns.some((t) => !t.answer)) return
    setTurns((t) => [...t, { question }])
    // A failed request is shown as the answer, so the chat never hangs.
    const asked = chosen.current
    const answer = await ask(question, asked).catch((error: Error) => ({ text: error.message, items: [], pairs: [] }))
    // The filters changed while it was waiting: the answer is about a network no longer shown.
    if (chosen.current !== asked) return
    setTurns((t) => [...t.slice(0, -1), { question, answer }])
    show(answer)
  }

  const lit: Lit = selected
    ? { items: [selected], pairs: partnersOf(network.pairs, selected).map((p) => ({ a: selected, b: p.name })) }
    : { items: shown?.items ?? [], pairs: shown?.pairs ?? [] }

  // The filters of the network on screen, named after the title.
  const scope = [loaded.days && PERIODS.find((p) => p.days === loaded.days)?.label, loaded.segment].filter(Boolean).join(", ")

  return (
    <main className="grid h-dvh grid-rows-[45dvh_minmax(0,1fr)] gap-3 p-3 lg:grid-cols-[minmax(0,1fr)_27rem] lg:grid-rows-1 lg:gap-5 lg:p-5">
      <div className={cn("grid min-h-0 transition-opacity", loading && "opacity-50")}>
        <Graph
          network={drawn}
          lit={lit}
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
          onSelect={(item) => (item ? setSelected(item === selected ? null : item) : show(null))}
        >
          <div className="pointer-events-none absolute top-5 left-5 max-w-[38%]">
            <Logo />
            <h1 className="mt-2 text-[20px] leading-tight font-bold text-black">
              {TITLE}
              {scope && ` (${scope})`}
            </h1>
            <p className="mt-1 text-[12px] text-ink-muted">
              {drawn.items.length} product types · {drawn.pairs.length} pairs
            </p>
          </div>
          {selected && <ItemCard network={network} name={selected} onSelect={setSelected} onAsk={send} />}
        </Graph>
      </div>
      <Chat
        turns={turns}
        shown={selected ? null : shown}
        onSend={send}
        onShow={show}
        onReset={() => {
          setTurns([])
          show(null)
        }}
      />
    </main>
  )
}
