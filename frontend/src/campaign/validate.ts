import type { FieldErrors, WizardDraft } from "./draft"

/*
 * The rules of backend/app/campaigns.py (draft_problems), with the same messages, plus the ranges
 * and lengths its Pydantic models check, so Next can stop a step before anything is sent. The
 * server's check still decides: it alone knows the catalog, and its today may differ near midnight.
 */

const MAX_TITLE = 200
const MAX_STRATEGY = 4000

const wholeIn = (value: number, low: number, high: number) => Number.isInteger(value) && value >= low && value <= high

/** The first problem per field is the one shown, as the server's problems are read. */
function add(errors: FieldErrors, key: string, message: string) {
  errors[key] ??= message
}

/** Missing, before today, or before the start it must follow. Dates are "YYYY-MM-DD", so they compare as text. */
function checkStart(errors: FieldErrors, key: string, value: string, today: string) {
  if (!value) add(errors, key, "Required.")
  else if (value < today) add(errors, key, "Must be today or later.")
}

function checkEnd(errors: FieldErrors, key: string, value: string, start: string) {
  if (!value) add(errors, key, "Required.")
  else if (start && value < start) add(errors, key, "Must be on or after the start date.")
}

function campaignErrors(draft: WizardDraft, today: string, errors: FieldErrors) {
  const title = draft.title.trim()
  const strategy = draft.strategy.trim()
  if (!title) add(errors, "title", "Required.")
  else if (title.length > MAX_TITLE) add(errors, "title", `At most ${MAX_TITLE} characters.`)
  if (!strategy) add(errors, "strategy", "Required.")
  else if (strategy.length > MAX_STRATEGY) add(errors, "strategy", `At most ${MAX_STRATEGY} characters.`)

  if (draft.products.length === 0) add(errors, "products", "Add at least one product.")
  const seen = new Set<string>()
  draft.products.forEach(({ kind, name }, i) => {
    const key = `${kind}|${name}`
    if (seen.has(key)) add(errors, `products.${i}`, "Listed twice.")
    seen.add(key)
  })

  if (!wholeIn(draft.discount_percent, 1, 100)) add(errors, "discount_percent", "Enter a whole number from 1 to 100.")
  checkStart(errors, "starts_on", draft.starts_on, today)
  checkEnd(errors, "ends_on", draft.ends_on, draft.starts_on)
}

function pilotErrors(draft: WizardDraft, today: string, errors: FieldErrors) {
  if (!draft.pilotOn) return
  const pilot = draft.pilot
  if (!wholeIn(pilot.audience_percent, 1, 99)) add(errors, "pilot.audience_percent", "Enter a whole number from 1 to 99.")
  checkStart(errors, "pilot.starts_on", pilot.starts_on, today)
  checkEnd(errors, "pilot.ends_on", pilot.ends_on, pilot.starts_on)
  // The pilot's result decides whether the campaign runs, so it must be over first.
  if (pilot.ends_on && draft.starts_on && pilot.ends_on >= draft.starts_on) add(errors, "pilot.ends_on", "Pilot must end before the campaign starts.")
  if (!wholeIn(pilot.discount_percent, 1, 100)) add(errors, "pilot.discount_percent", "Enter a whole number from 1 to 100.")
}

/** The problems of one step, by field. Step 3 is the review: steps 1 and 2 together. */
export function stepErrors(step: 1 | 2 | 3, draft: WizardDraft, today: string): FieldErrors {
  const errors: FieldErrors = {}
  if (step !== 2) campaignErrors(draft, today, errors)
  if (step !== 1) pilotErrors(draft, today, errors)
  return errors
}

const CAMPAIGN_FIELDS = ["title", "strategy", "products", "discount_percent", "starts_on", "ends_on", "segment", "counties"]

/** The step a field is on, or `null` for a problem no field shows (it is shown on the review). */
export function stepOf(key: string): 1 | 2 | null {
  if (key.startsWith("pilot.") || key === "pilot") return 2
  return CAMPAIGN_FIELDS.includes(key.split(".")[0]) ? 1 : null
}
