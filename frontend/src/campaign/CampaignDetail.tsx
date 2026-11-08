import { useRef, useState } from "react"
import { campaignAction, CampaignConflict, CampaignError, deleteCampaign } from "../api"
import { cn } from "../lib"
import type { SavedCampaign } from "../types"
import { CampaignTrend } from "./CampaignTrend"
import { dates, Pilot, Products, Row } from "./ReviewStep"
import { actionsFor, changedMessage, CONFIRM, MOVE_LABEL, STATUS_BADGE, STATUS_LABEL, type Move } from "./status"

const button = "h-9 cursor-pointer rounded-lg px-4 text-[14px] font-medium transition-colors disabled:cursor-default disabled:opacity-50"

/** The moves that push a campaign forward stand out; the rest are plain. */
const PRIMARY: Move[] = ["launch", "approve"]

const timeFormat = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" })

/** A status badge. */
export function StatusBadge({ status }: { status: SavedCampaign["status"] }) {
  return <span className={cn("shrink-0 rounded-full px-2 py-px text-[12px] font-medium", STATUS_BADGE[status])}>{STATUS_LABEL[status]}</span>
}

interface CampaignDetailProps {
  campaign: SavedCampaign
  onBack: () => void
  onEdit: () => void
  /** The campaign as the server now has it, after a move or a refused one. */
  onUpdated: (campaign: SavedCampaign) => void
  /** The campaign is no longer stored: deleted here, or by someone else. */
  onDeleted: () => void
  onToast: (message: string) => void
}

/**
 * Everything about one saved campaign, and what can be done to it now. A move names the status it
 * was shown with, so if someone else moved the campaign on in the meantime the server refuses it,
 * and this shows the campaign as it is now instead.
 */
export function CampaignDetail({ campaign, onBack, onEdit, onUpdated, onDeleted, onToast }: CampaignDetailProps) {
  const [pending, setPending] = useState(false)
  // State is too late to stop a double click: both clicks can run before a render.
  const acting = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const pilot = campaign.pilot
  // A pilot held for approval that never got it: the campaign itself never ran.
  const neverRan = campaign.status === "ended" && pilot !== null && !pilot.auto_start && campaign.approved_at === null
  const proposal = campaign.source_proposal

  const act = async (move: Move) => {
    if (move === "edit") return onEdit()
    if (acting.current) return
    const question = CONFIRM[move]
    if (question && !window.confirm(question)) return
    acting.current = true
    setPending(true)
    setError(null)
    try {
      if (move === "delete") {
        await deleteCampaign(campaign.id)
        onToast("Campaign deleted")
        onDeleted()
      } else {
        onUpdated(await campaignAction(campaign.id, move, campaign.status))
      }
    } catch (error) {
      if (error instanceof CampaignConflict) {
        onUpdated(error.campaign)
        onToast(changedMessage(error.campaign.status))
      } else if (error instanceof CampaignError && error.gone) {
        onToast(error.message)
        onDeleted()
      } else if (error instanceof CampaignError) {
        // A rule the server refused it on (a launch past its end date) says why; anything else, what failed.
        setError(error.fields ? Object.values(error.fields)[0] : error.message)
      } else {
        setError(`Could not ${move} the campaign. Try again.`)
      }
    } finally {
      acting.current = false
      setPending(false)
    }
  }

  const moves = actionsFor(campaign.status)
  const happened = [
    ["Created", campaign.created_at],
    ["Launched", campaign.launched_at],
    ["Approved", campaign.approved_at],
    ["Ended early", campaign.ended_at],
    ["Cancelled", campaign.cancelled_at],
  ].filter((entry): entry is [string, string] => entry[1] !== null)

  return (
    <div className="flex min-h-0 flex-col">
      <button type="button" onClick={onBack} className="mb-2 cursor-pointer self-start px-1 text-[13px] font-medium text-ink-muted hover:text-ink">
        ← All campaigns
      </button>
      <article className="flex min-h-0 flex-1 flex-col overflow-y-auto rounded-xl bg-surface-raised p-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-[18px] leading-snug font-semibold tracking-[-0.02em]">{campaign.title}</h3>
          <StatusBadge status={campaign.status} />
        </div>
        <dl className="mt-2">
          <Row term="Strategy">
            <span className="whitespace-pre-line">{campaign.strategy}</span>
          </Row>
          <Row term="Slogan">{campaign.slogan ?? "No slogan"}</Row>
          <Row term="Products">
            <Products products={campaign.products} />
          </Row>
          <Row term="Discount">{campaign.discount_percent}% off</Row>
          <Row term="Dates">{dates(campaign.starts_on, campaign.ends_on)}</Row>
          <Row term="Customers">{campaign.segment ?? "All customers"}</Row>
          <Row term="Counties">{campaign.counties.length === 0 ? "All counties" : campaign.counties.join(", ")}</Row>
          <Row term="Pilot">
            {pilot ? <Pilot pilot={pilot} /> : "No pilot"}
            {neverRan && <p className="mt-1 font-medium text-star-ink">Never ran: the pilot ended without approval.</p>}
          </Row>
          {happened.map(([term, at]) => (
            <Row key={term} term={term}>
              {timeFormat.format(new Date(at))}
            </Row>
          ))}
          <Row term="From proposal">
            {proposal ? (
              <ul>
                <li className="font-medium">
                  {proposal.name} <span className="text-[12px] font-normal text-ink-muted">{proposal.basis === "potential" ? "Potential · to test" : "Sells together today"}</span>
                </li>
                <li>
                  {proposal.items.join(" + ")}, {proposal.discount_percent}% off, for {proposal.audience ?? "all customers"}
                </li>
                <li className="text-[13px] text-ink-muted">{proposal.reason}</li>
              </ul>
            ) : (
              "Not from an AI proposal"
            )}
          </Row>
        </dl>
        <CampaignTrend campaign={campaign} />
        {error && (
          <p role="alert" className="mt-3 rounded-lg bg-star/15 px-3 py-2 text-[13px] text-star-ink">
            {error}
          </p>
        )}
        {moves.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
            {moves.map((move) => (
              <button
                key={move}
                type="button"
                disabled={pending}
                onClick={() => act(move)}
                className={cn(button, PRIMARY.includes(move) ? "bg-action text-on-action" : "bg-field hover:bg-line disabled:hover:bg-field")}
              >
                {MOVE_LABEL[move]}
              </button>
            ))}
          </div>
        )}
      </article>
    </div>
  )
}
