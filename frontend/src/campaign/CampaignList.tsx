import { useEffect, useState } from "react"
import { listCampaigns } from "../api"
import type { SavedCampaign } from "../types"
import { CampaignDetail, StatusBadge } from "./CampaignDetail"
import { dates } from "./ReviewStep"

interface CampaignListProps {
  /** Whether the tab is showing: the list is fetched again each time it opens. */
  active: boolean
  /** Goes up whenever a campaign was saved or moved, here or in the wizard: the list is fetched again. */
  version: number
  onEdit: (campaign: SavedCampaign) => void
  /** A campaign changed here. */
  onChanged: () => void
  onToast: (message: string) => void
}

/**
 * The Campaigns tab: every saved campaign, newest first, and one campaign's detail in its place
 * when a row is clicked. Statuses follow the date on the server, so the list is fetched again each
 * time the tab opens rather than kept.
 */
export function CampaignList({ active, version, onEdit, onChanged, onToast }: CampaignListProps) {
  const [campaigns, setCampaigns] = useState<SavedCampaign[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  /** The id of the campaign whose detail is open. */
  const [selected, setSelected] = useState<string | null>(null)

  // A change while the tab is hidden is fetched when it opens.
  useEffect(() => {
    if (!active) return
    let live = true
    listCampaigns().then(
      (loaded) => {
        if (!live) return
        setCampaigns(loaded)
        setFailed(false)
      },
      () => live && setFailed(true),
    )
    return () => {
      live = false
    }
  }, [active, version, attempt])

  // Read from the list, so a refetch shows the detail's campaign as it is now, and a deleted one closes.
  const open = campaigns?.find((c) => c.id === selected)
  const replace = (campaign: SavedCampaign) => setCampaigns((list) => list && list.map((c) => (c.id === campaign.id ? campaign : c)))

  return (
    <section aria-label="Campaigns" className="flex min-h-0 flex-col">
      <header className="flex h-10 shrink-0 items-start px-1">
        <h2 className="font-semibold">Campaigns</h2>
      </header>
      {open ? (
        <CampaignDetail
          key={open.id}
          campaign={open}
          onBack={() => setSelected(null)}
          onEdit={() => onEdit(open)}
          onUpdated={(campaign) => {
            replace(campaign)
            onChanged()
          }}
          onDeleted={() => {
            setCampaigns((list) => list && list.filter((c) => c.id !== open.id))
            setSelected(null)
            onChanged()
          }}
          onToast={onToast}
        />
      ) : failed ? (
        <div className="px-1 pt-2">
          <p role="alert" className="text-star-ink">
            Could not load campaigns.
          </p>
          <button type="button" onClick={() => setAttempt((n) => n + 1)} className="mt-2 h-9 cursor-pointer rounded-lg bg-field px-4 text-[14px] font-medium hover:bg-line">
            Retry
          </button>
        </div>
      ) : !campaigns ? (
        <p className="px-1 pt-2 text-ink-muted">Loading campaigns…</p>
      ) : campaigns.length === 0 ? (
        <p className="px-1 pt-2 text-ink-muted">No campaigns yet. Ask the chat for a strategy and add one.</p>
      ) : (
        // In the order the server sends them: newest first.
        <ul className="flex min-h-0 flex-col gap-2 overflow-y-auto">
          {campaigns.map((campaign) => (
            <li key={campaign.id}>
              <button type="button" onClick={() => setSelected(campaign.id)} className="w-full cursor-pointer rounded-xl bg-surface-raised p-4 text-left transition-colors hover:bg-field">
                <span className="flex items-start justify-between gap-3">
                  <span className="font-semibold">{campaign.title}</span>
                  <StatusBadge status={campaign.status} />
                </span>
                <span className="mt-1 block text-[13px] text-ink-muted">
                  {dates(campaign.starts_on, campaign.ends_on)} · {campaign.pilot ? `Pilot ${dates(campaign.pilot.starts_on, campaign.pilot.ends_on)}` : "No pilot"}
                </span>
                <span className="block text-[13px] text-ink-muted">
                  {campaign.discount_percent}% off · {campaign.products.length} {campaign.products.length === 1 ? "product" : "products"}
                </span>
                {campaign.slogan && <span className="mt-1 block text-[14px] font-medium">“{campaign.slogan}”</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
