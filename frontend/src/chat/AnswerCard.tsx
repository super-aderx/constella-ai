import { GenMark } from "../Brand"
import { callSummary, callText, citeParts, cn } from "../lib"
import type { Answer, Figure, Review, Strategy, ToolCall } from "../types"
import { Chart } from "./Chart"

const chip = "cursor-pointer rounded-full bg-field px-3 py-1.5 text-left text-[13px] transition-colors hover:bg-line"

/** Questions to ask, as quiet chips. */
export function Options({ options, onPick, className }: { options: string[]; onPick: (question: string) => void; className?: string }) {
  return (
    <ul className={cn("flex flex-wrap gap-2", className)}>
      {options.map((option) => (
        <li key={option}>
          <button type="button" onClick={() => onPick(option)} className={chip}>
            {option}
          </button>
        </li>
      ))}
    </ul>
  )
}

const sourceTag = "ml-0.5 text-[10px] font-medium text-ink-muted"

/** The answer's text, with each figure it states marked by the ledger entry it came from. */
function Cited({ text, figures }: { text: string; figures: Figure[] }) {
  if (figures.length === 0) return text
  // A figure may be written rounded, as the reviewer allows: 2.104 as 2.10.
  return citeParts(text, figures).map((part, i) =>
    part.figure ? (
      <span key={i} className="font-semibold tabular-nums">
        {part.text}
        <sup className={sourceTag}>{part.figure.source}</sup>
      </span>
    ) : (
      part.text
    ),
  )
}

/** What a tool call came back with, in a word or two: "8 rows". */
function resultSize(result: unknown) {
  if (Array.isArray(result)) return `${result.length} ${result.length === 1 ? "row" : "rows"}`
  return result && typeof result === "object" && "error" in result ? "nothing found" : null
}

/**
 * The tool calls behind an answer, in order, each on one line: its id, what it looked up, and how
 * much came back. A line opens to the call as it was made and its full result. The call a chart is
 * drawn from is marked.
 */
function Ledger({ ledger, charted }: { ledger: ToolCall[]; charted?: string }) {
  return (
    <details open className="rounded-xl bg-surface px-3 py-2 text-[12px]">
      <summary className="cursor-pointer font-semibold">
        {ledger.length} tool {ledger.length === 1 ? "call" : "calls"}
      </summary>
      <ol className="mt-1.5 flex flex-col gap-1">
        {ledger.map((entry) => (
          <li key={entry.id}>
            <details>
              <summary className="cursor-pointer">
                <b className="tabular-nums">{entry.id}</b> {callSummary(entry.tool, entry.args)}
                {resultSize(entry.result) && <span className="text-ink-muted"> · {resultSize(entry.result)}</span>}
                {entry.id === charted && <span className="ml-1.5 rounded-full bg-field px-1.5 py-px text-[10px] font-medium">drawn in the chart</span>}
              </summary>
              <div className="mt-1 mb-1.5 ml-3.5 border-l border-line pl-2.5">
                <code className="font-mono break-words">{callText(entry.tool, entry.args)}</code>
                <p className="max-h-24 overflow-y-auto break-words text-ink-muted">→ {JSON.stringify(entry.result)}</p>
              </div>
            </details>
          </li>
        ))}
      </ol>
    </details>
  )
}

/**
 * The reviewer's verdict: checked and sound, corrected after the reviewer sent it back (with what
 * it caught), or sent out with something still wrong.
 */
function Verdict({ review }: { review: Review }) {
  if (!review.passed) {
    return (
      <div className="rounded-xl bg-star/15 px-3 py-2 text-[12px] text-star-ink">
        <p className="font-semibold">! The reviewer could not confirm this answer</p>
        <ul className="mt-1 list-disc pl-4">
          {review.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </div>
    )
  }
  if (review.caught.length === 0) return <p className="text-[12px] text-positive">✓ Checked against the tool results</p>
  return (
    <details className="text-[12px] text-positive">
      <summary className="cursor-pointer">↻ Corrected after review</summary>
      <ul className="mt-1 list-disc pl-4 text-ink-muted">
        {review.caught.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </details>
  )
}

/** The strategist's part of an answer: what the options are, and each campaign as a card with the writer's slogans. */
function Campaigns({ strategy }: { strategy: Strategy }) {
  return (
    <section className="flex flex-col gap-3 border-t border-line pt-3">
      <p className="flex items-center gap-1.5 text-[12px] font-semibold text-ink-muted">
        <GenMark size={14} />
        Strategist
      </p>
      <p className="leading-6 text-pretty whitespace-pre-line">
        <Cited text={strategy.text} figures={strategy.figures} />
      </p>
      {strategy.campaigns.map((campaign, i) => (
        <div key={campaign.name} className="rounded-xl bg-surface p-4">
          <p className="flex items-center gap-2 text-[12px] font-medium text-ink-muted">
            Option {i + 1}
            {/* A bet on growth is marked: the data suggests it, nothing has proved it. */}
            <span className={cn("rounded-full px-2 py-px", campaign.basis === "potential" ? "bg-star/20 text-star-ink" : "bg-field")}>
              {campaign.basis === "potential" ? "Potential · to test" : "Sells together today"}
            </span>
          </p>
          <h3 className="mt-0.5 text-[18px] leading-snug font-semibold tracking-[-0.02em]">{campaign.name}</h3>
          <p className="mt-1.5 flex flex-wrap gap-1.5 text-[12px] font-semibold">
            <span className="rounded-md bg-action px-2 py-0.5 text-on-action">{campaign.discount_percent}% off</span>
            <span className="rounded-md bg-field px-2 py-0.5">{campaign.items.join(" + ")}</span>
            <span className="rounded-md bg-field px-2 py-0.5">{campaign.audience ?? "All customers"}</span>
          </p>
          {campaign.slogans.length > 0 && (
            <ul className="mt-3 flex flex-col gap-1 font-semibold">
              {campaign.slogans.map((slogan) => (
                <li key={slogan.text}>
                  “{slogan.text}”
                  {/* A pun is explained: it only lands when the sound is heard. */}
                  {slogan.pun && <span className="ml-2 text-[12px] font-normal text-ink-muted">{slogan.pun}</span>}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 border-t border-line pt-2 text-[12px] text-ink-muted">
            <Cited text={campaign.reason} figures={strategy.figures} />
          </p>
        </div>
      ))}
    </section>
  )
}

interface AnswerCardProps {
  answer: Answer
  /** What to ask after this answer. Empty when there is nothing to suggest. */
  next: string[]
  /** Asks one of the answer's suggested questions. */
  onAsk: (question: string) => void
  /** Whether the graph is showing this answer. */
  shown: boolean
  onShow: () => void
}

/** One answer from the agent: its text with cited figures, the tool calls behind it, a way to light it up on the graph, and what to ask next. */
export function AnswerCard({ answer, next, shown, onShow, onAsk }: AnswerCardProps) {
  return (
    <article className="flex flex-col gap-3 rounded-xl bg-surface-raised p-4">
      <p className="flex items-center gap-1.5 text-[12px] font-semibold text-ink-muted">
        <GenMark size={14} />
        Constella AI
      </p>
      <p className="leading-6 text-pretty whitespace-pre-line">
        <Cited text={answer.text} figures={answer.figures ?? []} />
      </p>
      {answer.options && answer.options.length > 0 && <Options options={answer.options} onPick={onAsk} />}
      {answer.strategy && <Campaigns strategy={answer.strategy} />}
      {answer.chart && answer.ledger && <Chart chart={answer.chart} ledger={answer.ledger} />}
      {answer.review && <Verdict review={answer.review} />}
      {answer.ledger && answer.ledger.length > 0 && <Ledger ledger={answer.ledger} charted={answer.chart?.source} />}
      {answer.items.length > 0 && (
        <button type="button" aria-pressed={shown} onClick={onShow} className={cn(chip, "self-start font-medium", shown && "bg-star/25 text-star-ink hover:bg-star/25")}>
          {shown ? "Shown on the graph" : "Show on the graph"}
        </button>
      )}
      {next.length > 0 && (
        <section className="flex flex-col gap-2 border-t border-line pt-3">
          <p className="text-[12px] font-semibold text-ink-muted">Next step</p>
          <Options options={next} onPick={onAsk} />
        </section>
      )}
    </article>
  )
}
