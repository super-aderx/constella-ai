import type { Campaign, CampaignDraft, PilotDraft } from "../types"

/**
 * A campaign while the wizard edits it. The pilot's values are always held, so switching the pilot
 * off and on again keeps what was typed; only `pilotOn` decides whether it is sent. An empty number
 * field is `NaN` and an empty date `""`, which the step checks report as missing.
 */
export type WizardDraft = Omit<CampaignDraft, "pilot"> & { pilotOn: boolean; pilot: PilotDraft }

/** Problems by field: the server's `loc` without "body", joined by ".", e.g. "pilot.ends_on", "products.2". */
export type FieldErrors = Record<string, string>

/** A pilot's starting values: a tenth of the audience, at the proposal's discount, held for approval when it passes. */
const PILOT_SIZE = 10

/** The draft a proposal opens the wizard with. The dates and counties are the team's to choose, so they start empty. */
export function fromProposal(proposal: Campaign): WizardDraft {
  return {
    source_proposal: proposal,
    client_token: crypto.randomUUID(),
    title: proposal.name,
    strategy: proposal.reason,
    products: proposal.items.map((name) => ({ kind: "type", name })),
    discount_percent: proposal.discount_percent,
    starts_on: "",
    ends_on: "",
    segment: proposal.audience,
    counties: [],
    pilotOn: false,
    pilot: { audience_percent: PILOT_SIZE, starts_on: "", ends_on: "", discount_percent: proposal.discount_percent, auto_start: false },
  }
}

/** The body to save: text trimmed, the pilot only when it is on, and the proposal's own fields without the slogans. */
export function toRequest(draft: WizardDraft): CampaignDraft {
  const { pilotOn, pilot, source_proposal: proposal, ...campaign } = draft
  return {
    ...campaign,
    source_proposal: proposal && {
      name: proposal.name,
      basis: proposal.basis,
      items: proposal.items,
      discount_percent: proposal.discount_percent,
      audience: proposal.audience,
      reason: proposal.reason,
    },
    title: draft.title.trim(),
    strategy: draft.strategy.trim(),
    pilot: pilotOn ? pilot : null,
  }
}

/** Whether anything was changed since the wizard opened. The token is not something the user changes. */
export function isDirty(a: WizardDraft, b: WizardDraft) {
  const plain = ({ client_token: _, ...rest }: WizardDraft) => JSON.stringify(rest)
  return plain(a) !== plain(b)
}

/** Today in the browser's timezone, as "YYYY-MM-DD". Not toISOString, which is UTC and can be a day off. */
export function today(now = new Date()) {
  return ymd(now.getFullYear(), now.getMonth() + 1, now.getDate())
}

const ymd = (y: number, m: number, d: number) => `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`

const dateFormat = new Intl.DateTimeFormat("en-US", { dateStyle: "medium" })

/** "2026-12-01" as "Dec 1, 2026". Built from its parts: `new Date("2026-12-01")` is UTC midnight, the day before west of Greenwich. */
export function formatDate(value: string) {
  const [y, m, d] = value.split("-").map(Number)
  return dateFormat.format(new Date(y, m - 1, d))
}
