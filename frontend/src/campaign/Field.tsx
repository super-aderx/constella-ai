import { useId, type ReactNode } from "react"
import { cn } from "../lib"
import type { FieldErrors, WizardDraft } from "./draft"

/* What the wizard's steps share: their props, field styles, and a labelled field with its problem. */

export interface StepProps {
  draft: WizardDraft
  errors: FieldErrors
  onChange: (patch: Partial<WizardDraft>) => void
}

export const input = "h-9 w-full rounded-lg border border-line bg-surface px-2.5 text-[14px] aria-[invalid=true]:border-star-ink"
export const caption = "text-[12px] font-medium text-ink-muted"
export const problem = "text-[12px] text-star-ink"

/** What a field's control needs to be labelled and tied to its problem. */
export interface FieldControl {
  id: string
  "aria-invalid": boolean
  "aria-describedby": string | undefined
}

/** A labelled field with its problem under it. The control gets the ids, so a screen reader reads the problem with it. */
export function Field({ label, error, className, children }: { label: string; error?: string; className?: string; children: (control: FieldControl) => ReactNode }) {
  const id = useId()
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <label htmlFor={id} className={caption}>
        {label}
      </label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": error ? `${id}-problem` : undefined })}
      {error && (
        <p id={`${id}-problem`} className={problem}>
          {error}
        </p>
      )}
    </div>
  )
}

/** A number field's value: `NaN` while it is empty, which the step check reports. */
export const numberValue = (value: number) => (Number.isNaN(value) ? "" : value)
export const readNumber = (text: string) => (text === "" ? NaN : Number(text))
