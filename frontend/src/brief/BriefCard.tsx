import { useState } from "react"
import { AnswerCard } from "../chat/AnswerCard"
import { chip, cn } from "../lib"
import type { Answer, Campaign, DepictCard } from "../types"

/**
 * The part of an answer a card shows folded: its first paragraph, which every Brief prompt asks
 * to be a takeaway of at most 3 lines. An answer that skipped the blank line shows its first 3.
 */
export function takeaway(text: string) {
  const trimmed = text.trim()
  const paragraphs = trimmed.split(/\n\s*\n/)
  return paragraphs.length > 1 ? paragraphs[0].trim() : trimmed.split("\n").slice(0, 3).join("\n")
}

const LEFT_OUT = "Uses a type you left out"

interface BriefCardProps {
  card: DepictCard
  /** Its place among the 8 questions, from 1. */
  number: number
  /** The product types this browser builds no campaign on. The Brief is answered without them, for everyone. */
  ignored: string[]
  /** The answer highlighted on the graph. */
  shown: Answer | null
  /** A chat answer is on its way: a turn added now would be taken for it. */
  chatBusy: boolean
  savedProposals: Map<Campaign, number>
  onShow: (answer: Answer) => void
  onContinue: (question: string, answer: Answer) => void
  /** Answers the card again. Settles once the server has taken the request. */
  onRefresh: () => Promise<void>
  onAddCampaign: (proposal: Campaign) => void
}

/**
 * One question of the Brief, in whatever state its answer is. An answered card shows its takeaway:
 * a click lights it up on the graph, and it opens to the full answer, with the campaigns it offers.
 */
export function BriefCard({ card, number, ignored, shown, chatBusy, savedProposals, onShow, onContinue, onRefresh, onAddCampaign }: BriefCardProps) {
  const [expanded, setExpanded] = useState(false)
  /** The refresh asked for and not yet taken by the server: a second click would only be refused. */
  const [asking, setAsking] = useState(false)
  const { answer, state } = card
  const isShown = answer !== null && answer === shown
  const busy = state === "waiting" || state === "answering" || asking
  const ideas = answer?.strategy?.campaigns.length ?? 0

  const refresh = async () => {
    setAsking(true)
    try {
      await onRefresh()
    } finally {
      setAsking(false)
    }
  }

  const refreshButton = (label: string) => (
    <button type="button" onClick={refresh} disabled={busy} className={cn(chip, "font-medium disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-field")}>
      {label}
    </button>
  )

  return (
    <article className={cn("flex flex-col gap-2 rounded-xl bg-surface-raised p-4", isShown && "ring-2 ring-star/60")}>
      <h3 className="flex gap-2 text-[14px] leading-snug font-semibold">
        <span className="text-ink-muted tabular-nums">{number}</span>
        {card.title}
      </h3>

      {state === "waiting" && <p className="text-[13px] text-ink-muted">Waiting…</p>}

      {state === "answering" && (
        <>
          <p className="text-[13px] text-ink-muted">Answering…</p>
          {answer && <p className="leading-6 whitespace-pre-line opacity-50">{takeaway(answer.text)}</p>}
        </>
      )}

      {state === "answered" && answer && (
        <>
          {/* The takeaway is the card's own "show on the graph". */}
          <button
            type="button"
            aria-pressed={isShown}
            onClick={() => onShow(answer)}
            title={isShown ? "Shown on the graph" : "Show on the graph"}
            className={cn("-mx-2 cursor-pointer rounded-lg px-2 py-1 text-left leading-6 whitespace-pre-line transition-colors hover:bg-field", isShown && "bg-star/25 hover:bg-star/25")}
          >
            {takeaway(answer.text)}
          </button>
          {ideas > 0 && !expanded && (
            <p className="text-[12px] text-ink-muted">
              {ideas} campaign {ideas === 1 ? "idea" : "ideas"}: expand to add one
            </p>
          )}
        </>
      )}

      {state === "no_data" && (
        <p className="text-[13px] text-ink-muted">
          <span className="font-semibold text-ink">Not enough data</span>
          {card.reason && ` · ${card.reason}`}
        </p>
      )}

      {state === "failed" && (
        <p className="text-[13px] text-ink-muted">
          <span className="font-semibold text-star-ink">Couldn't answer</span>
          {card.error && ` · ${card.error}`}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {state === "answered" && answer && (
          <>
            <button type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)} className={cn(chip, "font-medium")}>
              {expanded ? "Collapse" : "Expand"}
            </button>
            <button
              type="button"
              onClick={() => onContinue(card.title, answer)}
              disabled={chatBusy}
              title={chatBusy ? "Wait for the chat to finish answering" : undefined}
              className={cn(chip, "font-medium disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-field")}
            >
              Continue in chat
            </button>
          </>
        )}
        {(state === "answered" || state === "answering" || state === "no_data") && refreshButton("Refresh")}
        {state === "failed" && refreshButton("Retry")}
      </div>

      {state === "answered" && answer && expanded && (
        <AnswerCard
          // Its suggested questions are asked in the chat, once the card is carried there.
          answer={{ ...answer, options: undefined }}
          next={[]}
          onAsk={() => {}}
          shown={isShown}
          onShow={() => onShow(answer)}
          saved={(answer.strategy?.campaigns ?? []).map((campaign) => savedProposals.get(campaign) ?? 0)}
          onAddCampaign={(i) => onAddCampaign(answer.strategy!.campaigns[i])}
          // Answered for everyone, so it may build on a type this browser set aside (D3).
          blocked={(campaign) => (campaign.items.some((item) => ignored.includes(item)) ? LEFT_OUT : null)}
        />
      )}
    </article>
  )
}
