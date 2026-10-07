import { use, useState, useTransition } from "react"
import { ask, getNetwork } from "./api"
import { Logo } from "./Brand"
import { Chat } from "./chat/Chat"
import { Graph, type Lit } from "./graph/Graph"
import { ItemCard } from "./graph/ItemCard"
import { PERIODS, Toolbar } from "./graph/Toolbar"
import { cn, partnersOf } from "./lib"
import type { Answer, Filters, Mode, Turn } from "./types"

const TITLE = "高雄市 某零售商 產品並買圖"

/**
 * The two features side by side: the network graph and the chat. They are linked both ways:
 * an answer lights up its items and pairs on the graph, and a product type on the graph can be asked about.
 */
export default function App() {
  const [filters, setFilters] = useState<Filters>({ days: null, segment: null })
  const [mode, setMode] = useState<Mode>("community")
  /** A new filter keeps the old graph on screen, dimmed, until its network arrives. */
  const [loading, startTransition] = useTransition()
  const network = use(getNetwork(filters))
  const [turns, setTurns] = useState<Turn[]>([])
  /** The product type clicked on the graph. It takes over the highlight from `shown`. */
  const [selected, setSelected] = useState<string | null>(null)
  /** The answer highlighted on the graph. */
  const [shown, setShown] = useState<Answer | null>(null)

  const show = (answer: Answer | null) => {
    setSelected(null)
    setShown(answer)
  }

  // The selected type may not exist under the new filter, so the highlight is cleared with it.
  const filter = (next: Filters) =>
    startTransition(() => {
      setFilters(next)
      show(null)
    })

  // One question at a time, so only the last turn can be waiting.
  const send = async (question: string) => {
    if (turns.some((t) => !t.answer)) return
    setTurns((t) => [...t, { question }])
    // A failed request is shown as the answer, so the chat never hangs.
    const answer = await ask(question, filters).catch((error: Error) => ({ text: error.message, items: [], pairs: [] }))
    setTurns((t) => [...t.slice(0, -1), { question, answer }])
    show(answer)
  }

  const lit: Lit = selected
    ? { items: [selected], pairs: partnersOf(network.pairs, selected).map((p) => ({ a: selected, b: p.name })) }
    : { items: shown?.items ?? [], pairs: shown?.pairs ?? [] }

  // The active filters, named after the title.
  const scope = [filters.days && PERIODS.find((p) => p.days === filters.days)?.label, filters.segment].filter(Boolean).join(", ")

  return (
    <main className="grid h-dvh grid-rows-[45dvh_minmax(0,1fr)] gap-3 p-3 lg:grid-cols-[minmax(0,1fr)_27rem] lg:grid-rows-1 lg:gap-5 lg:p-5">
      <div className={cn("grid min-h-0 transition-opacity", loading && "opacity-50")}>
        <Graph
          network={network}
          lit={lit}
          mode={mode}
          toolbar={<Toolbar filters={filters} segments={network.segments} mode={mode} onFilters={filter} onMode={setMode} />}
          onSelect={(item) => (item ? setSelected(item === selected ? null : item) : show(null))}
        >
          <div className="pointer-events-none absolute top-5 left-5 max-w-[38%]">
            <Logo />
            <h1 className="mt-2 text-[20px] leading-tight font-bold text-black">
              {TITLE}
              {scope && ` (${scope})`}
            </h1>
            <p className="mt-1 text-[12px] text-ink-muted">
              {network.items.length} product types · {network.pairs.length} pairs
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
