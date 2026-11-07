import { cn } from "../lib"
import type { PilotDraft } from "../types"
import { Field, input, numberValue, problem, readNumber, type StepProps } from "./Field"

/** An on/off switch with its label beside it. */
function Switch({ on, label, onToggle }: { on: boolean; label: string; onToggle: (on: boolean) => void }) {
  return (
    <button type="button" role="switch" aria-checked={on} onClick={() => onToggle(!on)} className="flex cursor-pointer items-center gap-3 text-left text-[14px]">
      <span aria-hidden className={cn("relative h-5 w-9 shrink-0 rounded-full transition-colors", on ? "bg-action" : "bg-line")}>
        <span className={cn("absolute top-0.5 size-4 rounded-full bg-surface-raised transition-[left]", on ? "left-4.5" : "left-0.5")} />
      </span>
      {label}
    </button>
  )
}

/**
 * Step 2: an optional pilot on part of the audience before the campaign. Its fields show only while
 * it is on; switching it off keeps what was typed, but no pilot is sent.
 */
export function PilotStep({ draft, errors, onChange }: StepProps) {
  const pilot = draft.pilot
  const set = (patch: Partial<PilotDraft>) => onChange({ pilot: { ...pilot, ...patch } })
  return (
    <div className="flex flex-col gap-4">
      <Switch on={draft.pilotOn} label="Run a pilot first" onToggle={(pilotOn) => onChange({ pilotOn })} />
      {errors.pilot && <p className={problem}>{errors.pilot}</p>}
      {draft.pilotOn && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Pilot size, % of the audience" error={errors["pilot.audience_percent"]}>
              {(control) => (
                <input
                  {...control}
                  type="number"
                  min={1}
                  max={99}
                  step={1}
                  value={numberValue(pilot.audience_percent)}
                  onChange={(e) => set({ audience_percent: readNumber(e.target.value) })}
                  className={input}
                />
              )}
            </Field>
            <Field label="Pilot discount %" error={errors["pilot.discount_percent"]}>
              {(control) => (
                <input
                  {...control}
                  type="number"
                  min={1}
                  max={100}
                  step={1}
                  value={numberValue(pilot.discount_percent)}
                  onChange={(e) => set({ discount_percent: readNumber(e.target.value) })}
                  className={input}
                />
              )}
            </Field>
            <Field label="Pilot starts on" error={errors["pilot.starts_on"]}>
              {(control) => <input {...control} type="date" value={pilot.starts_on} onChange={(e) => set({ starts_on: e.target.value })} className={input} />}
            </Field>
            <Field label="Pilot ends on" error={errors["pilot.ends_on"]}>
              {(control) => <input {...control} type="date" value={pilot.ends_on} onChange={(e) => set({ ends_on: e.target.value })} className={input} />}
            </Field>
          </div>
          {/* Off holds the campaign for the team's approval once the pilot passes. */}
          <Switch on={pilot.auto_start} label="When the pilot passes: start the campaign automatically" onToggle={(auto_start) => set({ auto_start })} />
        </>
      )}
    </div>
  )
}
