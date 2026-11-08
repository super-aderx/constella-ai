import { useEffect, useRef, useState, type MouseEvent } from "react"
import { CampaignConflict, CampaignError, getCampaignOptions, saveCampaign, updateCampaign } from "../api"
import { cn } from "../lib"
import type { Campaign, CampaignOptions, SavedCampaign } from "../types"
import { CampaignStep } from "./CampaignStep"
import { fromProposal, fromSaved, isDirty, toRequest, today, type FieldErrors, type WizardDraft } from "./draft"
import { PilotStep } from "./PilotStep"
import { ReviewStep } from "./ReviewStep"
import { stepErrors, stepOf } from "./validate"

type StepNumber = 1 | 2 | 3

const STEPS: { n: StepNumber; label: string }[] = [
  { n: 1, label: "Campaign" },
  { n: 2, label: "Pilot" },
  { n: 3, label: "Review" },
]

const button = "h-9 cursor-pointer rounded-lg px-4 text-[14px] font-medium transition-colors disabled:cursor-default"

/**
 * What the wizard is open for: a new campaign from an AI proposal, or a saved draft to edit.
 * `alreadySaved` is how many campaigns were already saved from the proposal: more than none warns
 * before saving another.
 */
export type WizardMode = { kind: "create"; proposal: Campaign; alreadySaved: number } | { kind: "edit"; campaign: SavedCampaign }

interface CampaignWizardProps {
  mode: WizardMode
  onClose: () => void
  onSaved: (campaign: SavedCampaign) => void
  /** The draft being edited is no longer a draft: the server sent the campaign as it is now. */
  onConflict: (campaign: SavedCampaign) => void
  /** The draft being edited was deleted. */
  onGone: () => void
}

/** Whether a field's problem is still about what the field holds: it goes once the field is edited. */
function stillHolds(key: string, before: WizardDraft, after: WizardDraft) {
  const [field, part] = key.split(".")
  if (field === "pilot" && part) return before.pilotOn === after.pilotOn && before.pilot[part as keyof WizardDraft["pilot"]] === after.pilot[part as keyof WizardDraft["pilot"]]
  return before[field as keyof WizardDraft] === after[field as keyof WizardDraft]
}

/**
 * Turns an AI proposal into a campaign, or edits a saved draft, in a modal over the page: the
 * campaign (step 1), an optional pilot (step 2), and a review before saving (step 3). The draft
 * lives here, above the steps, so Back keeps every value. Each opening is one draft with its own
 * token, so a double click or a retry stores it once; saving the same proposal again on purpose
 * opens a new one. An edit replaces the draft by its id instead.
 */
export function CampaignWizard({ mode, onClose, onSaved, onConflict, onGone }: CampaignWizardProps) {
  const [initial] = useState(() => (mode.kind === "create" ? fromProposal(mode.proposal) : fromSaved(mode.campaign)))
  // A stored campaign keeps its proposal without the slogans, so only a new one has any to offer.
  const slogans = mode.kind === "create" ? mode.proposal.slogans.map((slogan) => slogan.text) : []
  const [draft, setDraft] = useState(initial)
  const [step, setStep] = useState<StepNumber>(1)
  // The step checks' problems, and the server's. The server's are kept apart because Next cannot
  // check them again (the catalog is only on the server): they stay, and stop Next, until their
  // field is edited.
  const [errors, setErrors] = useState<FieldErrors>({})
  const [serverErrors, setServerErrors] = useState<FieldErrors>({})
  const [saveError, setSaveError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  // A save that failed without saying why may have been stored all the same. Its token now stands
  // for those values, so they are locked (no Back) until a retry of the same request gets an answer.
  const [locked, setLocked] = useState(false)
  // State is too late to stop a double click: both clicks can run before a render.
  const saving = useRef(false)
  const [options, setOptions] = useState<CampaignOptions | null>(null)
  const [optionsFailed, setOptionsFailed] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  // Where a click began: one that starts in a field and ends on the backdrop is not a click on the backdrop.
  const pressed = useRef<EventTarget | null>(null)

  useEffect(() => {
    if (!dialog.current?.open) dialog.current?.showModal()
  }, [])

  useEffect(() => {
    let live = true
    getCampaignOptions().then(
      (loaded) => live && setOptions(loaded),
      () => live && setOptionsFailed(true),
    )
    return () => {
      live = false
    }
  }, [])

  const change = (patch: Partial<WizardDraft>) => {
    const next = { ...draft, ...patch }
    setDraft(next)
    const kept = (found: FieldErrors) => Object.fromEntries(Object.entries(found).filter(([key]) => stillHolds(key, draft, next)))
    setErrors(kept(errors))
    setServerErrors(kept(serverErrors))
  }

  const requestClose = () => {
    if (saving.current) return
    if (isDirty(initial, draft) && !window.confirm("Discard this campaign draft?")) return
    onClose()
  }

  const goNext = () => {
    const found = stepErrors(step, draft, today())
    setErrors(found)
    const unfixed = Object.keys(serverErrors).some((key) => stepOf(key) === step)
    if (Object.keys(found).length === 0 && !unfixed) setStep((step + 1) as StepNumber)
  }

  const goBack = () => setStep((step - 1) as StepNumber)

  /** Goes to the first step that has a field for one of the problems; problems no field shows are put on the review. */
  const showProblems = (found: FieldErrors, message: string) => {
    const keys = Object.keys(found)
    const steps = keys.map(stepOf).filter((n) => n !== null)
    const unplaced = keys.filter((key) => stepOf(key) === null).map((key) => found[key])
    setSaveError(unplaced.length > 0 ? unplaced.join(" ") : steps.length > 0 ? null : message)
    setStep(steps.length > 0 ? (Math.min(...steps) as StepNumber) : 3)
  }

  const save = async () => {
    if (saving.current) return
    if (mode.kind === "create" && mode.alreadySaved > 0 && !window.confirm("You already saved a campaign from this proposal. Save another?")) return
    const found = stepErrors(3, draft, today())
    if (Object.keys(found).length > 0) {
      setErrors(found)
      return showProblems(found, "")
    }
    saving.current = true
    setPending(true)
    setSaveError(null)
    try {
      const request = toRequest(draft)
      const saved = mode.kind === "create" ? await saveCampaign(request) : await updateCampaign(mode.campaign.id, request)
      onSaved(saved)
    } catch (error) {
      // The draft and its token are kept: a retry cannot store the campaign twice.
      saving.current = false
      setPending(false)
      // Nothing here can be saved any more: the wizard closes, and the list is put right.
      if (error instanceof CampaignConflict) return onConflict(error.campaign)
      if (error instanceof CampaignError && error.gone) return onGone()
      if (error instanceof CampaignError && error.fields) {
        // A 422 stored nothing, so the values can be changed again.
        setLocked(false)
        setServerErrors(error.fields)
        showProblems(error.fields, error.message)
      } else {
        setLocked(true)
        const message = error instanceof Error ? error.message : String(error)
        setSaveError(`${message} The values are locked because the last attempt may have been saved.`)
      }
    }
  }

  // The server's problem is shown over the step check's for the same field: it knows more.
  const shown = { ...errors, ...serverErrors }

  const onBackdrop = (e: MouseEvent) => {
    if (e.target === dialog.current && pressed.current === dialog.current) requestClose()
  }

  return (
    <dialog
      ref={dialog}
      aria-labelledby="campaign-wizard-title"
      // Escape is handled on the key, not on `cancel`: some browsers stop letting a repeated cancel be prevented.
      onKeyDown={(e) => {
        if (e.key !== "Escape") return
        e.preventDefault()
        requestClose()
      }}
      onCancel={(e) => {
        e.preventDefault()
        requestClose()
      }}
      onMouseDown={(e) => (pressed.current = e.target)}
      onClick={onBackdrop}
      // Tailwind's base styles zero the margin that centers a dialog, so it is put back.
      className="m-auto max-h-[calc(100vh-2rem)] w-[min(640px,calc(100vw-2rem))] overflow-hidden rounded-xl bg-surface-raised p-0 text-ink shadow-pop backdrop:bg-ink/40"
    >
      <div className="flex max-h-[calc(100vh-2rem)] flex-col">
        <header className="flex flex-col gap-3 border-b border-line px-6 pt-5 pb-4">
          <div className="flex items-start justify-between gap-4">
            <h2 id="campaign-wizard-title" className="text-[18px] font-semibold tracking-[-0.02em]">
              {mode.kind === "create" ? "Add as campaign" : "Edit campaign"}
            </h2>
            <button type="button" aria-label="Close" onClick={requestClose} className="cursor-pointer px-1 text-[20px] leading-none text-ink-muted hover:text-ink">
              ×
            </button>
          </div>
          <ol className="flex items-center gap-2 text-[13px]">
            {STEPS.map(({ n, label }, i) => (
              <li key={n} aria-current={n === step ? "step" : undefined} className={cn("flex items-center gap-2", n === step ? "font-semibold text-ink" : "text-ink-muted")}>
                {i > 0 && <span aria-hidden>·</span>}
                <span className={cn("inline-grid size-5 place-items-center rounded-full text-[11px]", n === step ? "bg-action text-on-action" : "bg-field")}>{n}</span>
                {label}
              </li>
            ))}
          </ol>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {step === 1 && <CampaignStep draft={draft} errors={shown} onChange={change} options={options} optionsFailed={optionsFailed} today={today()} slogans={slogans} />}
          {step === 2 && <PilotStep draft={draft} errors={shown} onChange={change} />}
          {step === 3 && <ReviewStep draft={draft} error={saveError} />}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-line px-6 py-4">
          {step > 1 && (
            <button type="button" onClick={goBack} disabled={pending || locked} className={cn(button, "mr-auto bg-field hover:bg-line disabled:opacity-50 disabled:hover:bg-field")}>
              Back
            </button>
          )}
          {step < 3 ? (
            <button type="button" onClick={goNext} className={cn(button, "bg-action text-on-action")}>
              Next
            </button>
          ) : (
            <button type="button" onClick={save} disabled={pending} className={cn(button, "bg-action text-on-action disabled:bg-field disabled:text-ink-faint")}>
              {pending ? "Saving…" : "Save"}
            </button>
          )}
        </footer>
      </div>
    </dialog>
  )
}
