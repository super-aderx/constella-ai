import type { FieldErrors } from "./campaign/draft"
import type { Answer, CampaignAction, CampaignDraft, CampaignOptions, CampaignStatus, Earlier, Filters, Network, ProductHit, SavedCampaign, Step } from "./types"

/** The backend's endpoints. Vite proxies /api to it (see vite.config.ts). */

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  if (!response.ok) throw new Error(`The API answered ${response.status} for ${path}. Is the backend running?`)
  return response.json()
}

const networks = new Map<string, Promise<Network>>()

/** The network for one filter. Each filter is fetched once, so the same promise can be read on every render. */
export function getNetwork({ days, segment }: Filters) {
  const query = new URLSearchParams()
  if (days) query.set("days", String(days))
  if (segment) query.set("segment", segment)
  const path = `/network?${query}`
  if (!networks.has(path)) networks.set(path, request<Network>(path))
  return networks.get(path)!
}

/**
 * Asks the agent about the network the filters show. `ignored` are the product types it must build
 * no campaign on, and `history` the turns before it, so a follow-up can be read. The answer comes as
 * a stream of JSON lines: each step of the run as it starts, passed to `onStep`, then the answer.
 */
export async function ask(question: string, filters: Filters, ignored: string[], history: Earlier[], onStep: (step: Step) => void): Promise<Answer> {
  const path = "/ask/stream"
  const response = await fetch(`/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, ...filters, ignored, history }) })
  if (!response.ok || !response.body) throw new Error(`The API answered ${response.status} for ${path}. Is the backend running?`)
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  // A chunk can end mid-line: the unfinished part waits for the next one.
  let rest = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    const lines = (rest + value).split("\n")
    rest = lines.pop()!
    for (const line of lines.filter(Boolean)) {
      const event: Step | { answer: Answer } | { error: string } = JSON.parse(line)
      if ("step" in event) onStep(event)
      else if ("answer" in event) return event.answer
      else throw new Error(event.error)
    }
  }
  throw new Error("The answer was cut off before it arrived. Is the backend running?")
}

let campaignOptions: Promise<CampaignOptions> | null = null

/** The segments and counties a campaign can target, fetched once. A failure is not kept, so the next wizard retries. */
export function getCampaignOptions() {
  campaignOptions ??= request<CampaignOptions>("/campaign-options").catch((error: unknown) => {
    campaignOptions = null
    throw error
  })
  return campaignOptions
}

/** Product types and products that match what was typed, typos allowed; the best 20. */
export function searchProducts(q: string, signal: AbortSignal) {
  return request<ProductHit[]>(`/products/search?${new URLSearchParams({ q, limit: "20" })}`, { signal })
}

const SAVE_FAILED = "Could not save the campaign. Try again."
const GONE = "This campaign was deleted."

/**
 * Why a campaign request failed. `fields` holds the server's problems by field ("title",
 * "pilot.ends_on", "products.2", "action"), or is `null` when it failed for another reason.
 * `gone` is set when the campaign no longer exists (404).
 */
export class CampaignError extends Error {
  fields: FieldErrors | null
  gone: boolean
  constructor(message: string, fields: FieldErrors | null, gone = false) {
    super(message)
    this.fields = fields
    this.gone = gone
  }
}

/**
 * The campaign changed since it was shown (someone else acted on it, or it left Draft), so the
 * request was refused. The server sends the campaign as it is now, so the row can be put right
 * without asking again.
 */
export class CampaignConflict extends Error {
  campaign: SavedCampaign
  constructor(message: string, campaign: SavedCampaign) {
    super(message)
    this.campaign = campaign
  }
}

const json = { "Content-Type": "application/json" }

/**
 * A campaign request, with its failures turned into a `CampaignError` or `CampaignConflict`.
 * `failed` is the message for a failure the server did not explain.
 */
async function campaignRequest(path: string, init: RequestInit, failed: string): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, init)
  } catch {
    throw new CampaignError(failed, null)
  }
  if (response.ok) return response
  // Only a path with an id can name a campaign that is gone; elsewhere a 404 is a missing route.
  if (response.status === 404 && path.startsWith("/campaigns/")) throw new CampaignError(GONE, null, true)
  const body: { detail?: unknown; campaign?: SavedCampaign } | null = response.status === 409 || response.status === 422 ? await response.json().catch(() => null) : null
  if (response.status === 409 && body?.campaign) throw new CampaignConflict(typeof body.detail === "string" ? body.detail : failed, body.campaign)
  const detail = body?.detail
  if (response.status !== 422 || !Array.isArray(detail)) throw new CampaignError(failed, null)
  // FastAPI's shape for both its own checks and the campaign rules: the first problem per field is shown.
  const fields: FieldErrors = {}
  for (const { loc, msg } of detail as { loc: (string | number)[]; msg: string }[]) {
    const key = loc.filter((part, i) => !(i === 0 && part === "body")).join(".")
    fields[key] ??= msg
  }
  throw new CampaignError("Fix the marked fields.", fields)
}

/**
 * Stores a campaign as a draft. A 200 is a success too: a campaign with this draft's token was
 * already stored, by a double click or a retry, and comes back unchanged.
 */
export async function saveCampaign(draft: CampaignDraft): Promise<SavedCampaign> {
  const response = await campaignRequest("/campaigns", { method: "POST", headers: json, body: JSON.stringify(draft) }, SAVE_FAILED)
  return response.json()
}

/** Every campaign, newest first. */
export function listCampaigns() {
  return request<SavedCampaign[]>("/campaigns")
}

/** Replaces a draft's values. Only a draft can be edited: anything else is a `CampaignConflict`. */
export async function updateCampaign(id: string, draft: CampaignDraft): Promise<SavedCampaign> {
  const response = await campaignRequest(`/campaigns/${encodeURIComponent(id)}`, { method: "PUT", headers: json, body: JSON.stringify(draft) }, SAVE_FAILED)
  return response.json()
}

/** Deletes a draft. Only a draft can be deleted: anything else is a `CampaignConflict`. */
export async function deleteCampaign(id: string): Promise<void> {
  await campaignRequest(`/campaigns/${encodeURIComponent(id)}`, { method: "DELETE" }, "Could not delete the campaign. Try again.")
}

/**
 * Moves a campaign on. `expected` is the status it was shown with: if it has changed since, the
 * server refuses with a `CampaignConflict`, so a stale screen never acts on a campaign it no
 * longer shows.
 */
export async function campaignAction(id: string, action: CampaignAction, expected: CampaignStatus): Promise<SavedCampaign> {
  const response = await campaignRequest(
    `/campaigns/${encodeURIComponent(id)}/actions`,
    { method: "POST", headers: json, body: JSON.stringify({ action, expected }) },
    `Could not ${action} the campaign. Try again.`,
  )
  return response.json()
}
