import { cn } from "../lib"
import type { CampaignOptions } from "../types"
import { caption, Field, input, numberValue, problem, readNumber, type StepProps } from "./Field"
import { ProductPicker } from "./ProductPicker"

interface CampaignStepProps extends StepProps {
  /** `null` while loading or when it failed. */
  options: CampaignOptions | null
  optionsFailed: boolean
  today: string
  /** The proposal's AI slogans, offered to pick and edit. Empty for none, and when editing a saved campaign. */
  slogans: string[]
}

/** Step 1: what the campaign is, what it covers, when, and for whom. */
export function CampaignStep({ draft, errors, onChange, options, optionsFailed, today, slogans }: CampaignStepProps) {
  // A segment the proposal named stays offered even if the list lacks it: the server's check marks it on Save.
  const segments = options?.segments ?? []
  const shownSegments = draft.segment && !segments.includes(draft.segment) ? [draft.segment, ...segments] : segments
  const countyProblems = Object.entries(errors).filter(([key]) => key === "counties" || key.startsWith("counties."))

  return (
    <div className="flex flex-col gap-4">
      <Field label="Title" error={errors.title}>
        {(control) => <input {...control} value={draft.title} maxLength={200} onChange={(e) => onChange({ title: e.target.value })} className={input} />}
      </Field>
      <Field label="Strategy" error={errors.strategy}>
        {(control) => (
          <textarea
            {...control}
            value={draft.strategy}
            maxLength={4000}
            rows={3}
            onChange={(e) => onChange({ strategy: e.target.value })}
            className={cn(input, "h-auto py-2 leading-6 [field-sizing:content]")}
          />
        )}
      </Field>
      <Field label="Slogan (optional)" error={errors.slogan}>
        {(control) => (
          <>
            <input
              {...control}
              value={draft.slogan}
              maxLength={100}
              placeholder={slogans.length > 0 ? "Pick one below and edit it, or write your own" : "Write one, or leave it empty"}
              onChange={(e) => onChange({ slogan: e.target.value })}
              className={input}
            />
            {/* Picking one copies it into the field, so it can be edited; the others stay on offer. */}
            {slogans.length > 0 && (
              <div className="flex flex-wrap gap-1.5" aria-label="AI slogans">
                {slogans.map((slogan) => (
                  <button
                    key={slogan}
                    type="button"
                    aria-pressed={draft.slogan === slogan}
                    onClick={() => onChange({ slogan })}
                    className={cn("cursor-pointer rounded-full px-2.5 py-0.5 text-[13px] transition-colors", draft.slogan === slogan ? "bg-action text-on-action" : "bg-field hover:bg-line")}
                  >
                    {slogan}
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </Field>
      <Field label="Products" error={errors.products}>
        {(control) => <ProductPicker control={control} value={draft.products} errors={errors} onChange={(products) => onChange({ products })} />}
      </Field>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Discount %" error={errors.discount_percent}>
          {(control) => (
            <input
              {...control}
              type="number"
              min={1}
              max={100}
              step={1}
              value={numberValue(draft.discount_percent)}
              onChange={(e) => onChange({ discount_percent: readNumber(e.target.value) })}
              className={input}
            />
          )}
        </Field>
        <Field label="Starts on" error={errors.starts_on}>
          {(control) => <input {...control} type="date" min={today} value={draft.starts_on} onChange={(e) => onChange({ starts_on: e.target.value })} className={input} />}
        </Field>
        <Field label="Ends on" error={errors.ends_on}>
          {(control) => (
            <input {...control} type="date" min={draft.starts_on || today} value={draft.ends_on} onChange={(e) => onChange({ ends_on: e.target.value })} className={input} />
          )}
        </Field>
      </div>
      <Field label="Customer segment" error={errors.segment}>
        {(control) => (
          <select {...control} value={draft.segment ?? ""} onChange={(e) => onChange({ segment: e.target.value || null })} className={cn(input, "cursor-pointer")}>
            <option value="">All customers</option>
            {shownSegments.map((segment) => (
              <option key={segment}>{segment}</option>
            ))}
          </select>
        )}
      </Field>
      <fieldset className="flex flex-col gap-1">
        <legend className={caption}>Counties</legend>
        {optionsFailed ? (
          <p className={problem}>Could not load the counties. Close and reopen to try again.</p>
        ) : !options ? (
          <p className="text-[13px] text-ink-muted">Loading counties…</p>
        ) : (
          <details className="rounded-lg border border-line bg-surface text-[14px]">
            <summary className="cursor-pointer px-2.5 py-1.5">{draft.counties.length === 0 ? "All counties" : `${draft.counties.length} selected`}</summary>
            <ul className="max-h-40 overflow-y-auto border-t border-line px-2.5 py-1.5">
              {options.counties.map((county) => (
                <li key={county}>
                  <label className="flex cursor-pointer items-center gap-2 py-0.5">
                    <input
                      type="checkbox"
                      checked={draft.counties.includes(county)}
                      onChange={(e) => onChange({ counties: e.target.checked ? [...draft.counties, county] : draft.counties.filter((c) => c !== county) })}
                    />
                    {county}
                  </label>
                </li>
              ))}
            </ul>
          </details>
        )}
        {countyProblems.map(([key, message]) => (
          <p key={key} className={problem}>
            {message}
          </p>
        ))}
      </fieldset>
    </div>
  )
}
