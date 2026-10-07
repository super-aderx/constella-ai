import { fmt, partnersOf } from "../lib"
import type { Network } from "../types"
import { communityColor } from "./Graph"

interface ItemCardProps {
  network: Network
  /** The selected product type's name. */
  name: string
  onSelect: (item: string | null) => void
  onAsk: (question: string) => void
}

/** The selected product type: its figures, its top products, its strongest partners, and a way to ask about it. */
export function ItemCard({ network, name, onSelect, onAsk }: ItemCardProps) {
  const item = network.items.find((i) => i.name === name)!
  const partners = partnersOf(network.pairs, name).slice(0, 4)
  return (
    <aside className="absolute right-4 bottom-4 flex max-h-[calc(100%-2rem)] w-64 flex-col gap-3 overflow-y-auto rounded-xl border border-line bg-surface-raised p-4 text-[13px] shadow-pop">
      <header>
        <p className="flex items-center gap-1.5 text-[12px] text-ink-muted">
          <span className="size-2.5 rounded-full" style={{ background: communityColor(item.community) }} />
          {item.community == null ? "No group" : network.communities[item.community]}
          <button type="button" aria-label="Close" onClick={() => onSelect(null)} className="ml-auto cursor-pointer px-1 text-[16px] leading-none">
            ×
          </button>
        </p>
        <h2 className="mt-1 text-[17px] font-semibold tracking-[-0.02em]">{item.name}</h2>
        <p className="text-ink-muted tabular-nums">
          {fmt.int(item.orders)} orders · {fmt.money(item.revenue)}
        </p>
      </header>

      <section className="border-t border-line pt-2">
        <h3 className="text-[12px] font-medium text-ink-muted">Top products</h3>
        <ul>
          {item.products.map((p) => (
            <li key={p.name} className="flex justify-between gap-2 py-1">
              <span className="truncate">{p.name}</span>
              <span className="shrink-0 text-ink-muted tabular-nums">{fmt.int(p.orders)} orders</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="border-t border-line pt-2">
        <h3 className="text-[12px] font-medium text-ink-muted">Bought with</h3>
        <ul>
        {partners.map((p) => (
          <li key={p.name}>
            <button type="button" onClick={() => onSelect(p.name)} className="flex w-full cursor-pointer justify-between gap-2 rounded-md py-1 text-left hover:bg-field">
              <span className="truncate">{p.name}</span>
              <span className="text-ink-muted tabular-nums">{fmt.lift(p.lift)}</span>
            </button>
          </li>
        ))}
        </ul>
      </section>

      <button type="button" onClick={() => onAsk(`What sells with ${item.name}?`)} className="h-9 cursor-pointer rounded-lg bg-action font-semibold text-on-action">
        Ask about it
      </button>
    </aside>
  )
}
