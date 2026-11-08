import type { Answer, Campaign, Filters } from "../types"
import { BriefCard } from "./BriefCard"
import { useDepict } from "./useDepict"

interface BriefProps {
  /** The scope the graph shows: the Brief is always about it. */
  filters: Filters
  /** That scope in words: "Last 90 days, 忠誠客戶". */
  label: string
  ignored: string[]
  shown: Answer | null
  chatBusy: boolean
  savedProposals: Map<Campaign, number>
  onShow: (answer: Answer) => void
  /** Carries a card into the chat as its latest turn. */
  onContinue: (question: string, answer: Answer) => void
  onAddCampaign: (proposal: Campaign) => void
  onToast: (message: string) => void
}

/**
 * The Brief tab: the 8 standard questions answered for the scope on screen. It stays mounted while
 * another tab shows, so the answers keep coming in out of sight.
 */
export function Brief({ filters, label, ignored, shown, chatBusy, savedProposals, onShow, onContinue, onAddCampaign, onToast }: BriefProps) {
  const { depict, trouble, refresh } = useDepict(filters)
  const answered = depict?.cards.filter((c) => c.state === "answered").length ?? 0

  return (
    <section className="flex min-h-0 flex-col gap-3">
      <header className="shrink-0 px-1">
        <p className="flex flex-wrap items-baseline gap-x-2 text-[14px] font-semibold">
          {label}
          <span className="text-[12px] font-normal text-ink-muted">· {depict ? `${answered} of ${depict.cards.length} answered` : "Starting…"}</span>
        </p>
        {trouble && <p className="mt-1 text-[12px] text-star-ink">{trouble}</p>}
      </header>
      {depict && (
        <ol className="flex min-h-0 flex-col gap-3 overflow-y-auto pb-3">
          {depict.cards.map((card, i) => (
            <li key={card.key}>
              <BriefCard
                card={card}
                number={i + 1}
                ignored={ignored}
                shown={shown}
                chatBusy={chatBusy}
                savedProposals={savedProposals}
                onShow={onShow}
                onContinue={onContinue}
                onRefresh={() => refresh(card.key).catch(() => onToast("Couldn't refresh this card. Try again."))}
                onAddCampaign={onAddCampaign}
              />
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
