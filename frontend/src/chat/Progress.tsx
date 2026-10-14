import { callSummary } from "../lib"
import type { Step } from "../types"

/** Each role's step, as the user reads it: what is being done, and why the run does it. */
const STEPS: Record<string, { title: string; why: (step: Step) => string }> = {
  router: {
    title: "Planning the run",
    why: () => "Deciding whether this is a question about the store's sales, and whether its answer needs a campaign or a chart.",
  },
  analyst: {
    title: "Looking up the data",
    why: () => "Every figure in the answer has to come from a tool result, so the analyst looks each one up and never recalls or works one out.",
  },
  review: {
    title: "Checking the answer",
    why: () => "Each figure is compared with the tool result it cites before the answer is sent.",
  },
  fix: {
    title: "Correcting the answer",
    why: (step) => `The check found ${things(step.notes)} it could not confirm, so the analyst is answering again with ${step.notes === 1 ? "it" : "them"} fixed.`,
  },
  strategist: {
    title: "Drafting campaigns",
    why: () => "You asked for something to do with the findings, so the strategist is turning them into two or three options that differ.",
  },
  strategy_review: {
    title: "Checking the campaigns",
    why: () => "Each campaign has to be one that can run as written: product types that sell together, a discount in range, a real segment.",
  },
  strategy_fix: {
    title: "Correcting the campaigns",
    why: (step) => `The check found ${things(step.notes)} that could not go out as written, so the strategist is drafting again.`,
  },
  writer: {
    title: "Writing slogans",
    why: () => "The campaigns passed their check, so the writer is wording a few slogans for each. It cannot change an offer.",
  },
  scientist: {
    title: "Choosing a chart",
    why: () => "Deciding whether a chart would show more than the text does. If so, it is drawn from a tool result, never from typed numbers.",
  },
}

const things = (count = 0) => `${count} ${count === 1 ? "thing" : "things"}`

/** A role's step with the tool calls made during it. */
interface Phase {
  step: Step
  calls: Step[]
}

/** The steps as phases: each role starts one, and a tool call belongs to the role that made it. */
function phases(steps: Step[]) {
  const found: Phase[] = []
  for (const step of steps) {
    if (step.step !== "tool") found.push({ step, calls: [] })
    else found[found.length - 1]?.calls.push(step)
  }
  // A step this app has no words for is left out.
  return found.filter((phase) => phase.step.step in STEPS)
}

/**
 * A run in progress: the steps finished, each on one line, then the current one with why the run
 * does it and the lookup it is making now. Before the first step arrives, only that it has started.
 */
export function Progress({ steps }: { steps: Step[] }) {
  const all = phases(steps)
  const current = all[all.length - 1]
  const call = current?.calls[current.calls.length - 1]
  return (
    <div aria-live="polite" className="flex flex-col gap-2 rounded-xl bg-surface-raised p-4 text-[13px]">
      {!current && <span className="text-ink-muted">Reading the data…</span>}
      {all.slice(0, -1).map(({ step, calls }, i) => (
        <p key={i} className="flex gap-2 text-ink-muted">
          <span aria-hidden className="w-3 text-positive">
            ✓
          </span>
          {STEPS[step.step].title}
          {calls.length > 0 && ` · ${calls.length} ${calls.length === 1 ? "lookup" : "lookups"}`}
        </p>
      ))}
      {current && (
        <div className="flex gap-2">
          <span aria-hidden className="mt-1.5 ml-0.5 size-2 shrink-0 animate-pulse rounded-full bg-star" />
          <div className="ml-0.5 min-w-0">
            <p className="font-semibold">{STEPS[current.step.step].title}…</p>
            <p className="mt-0.5 text-[12px] text-ink-muted">{STEPS[current.step.step].why(current.step)}</p>
            {call?.tool && (
              <p className="mt-1.5 text-[12px] break-words">
                <span className="text-ink-muted">Now {call.id}:</span> {callSummary(call.tool, call.args ?? {})}
              </p>
            )}
          </div>
        </div>
      )}
      {[78, 54].map((w) => (
        <span key={w} className="h-3 animate-pulse rounded-sm bg-field" style={{ width: `${w}%` }} />
      ))}
    </div>
  )
}
