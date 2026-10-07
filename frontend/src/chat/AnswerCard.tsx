import { GenMark } from "../Brand"
import { cn } from "../lib"
import type { Answer } from "../types"

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

interface AnswerCardProps {
  answer: Answer
  /** Whether the graph is showing this answer. */
  shown: boolean
  onShow: () => void
}

/** One answer from the agent, and a way to light up what it names on the graph. */
export function AnswerCard({ answer, shown, onShow }: AnswerCardProps) {
  return (
    <article className="flex flex-col gap-3 rounded-xl bg-surface-raised p-4">
      <p className="flex items-center gap-1.5 text-[12px] font-semibold text-ink-muted">
        <GenMark size={14} />
        Constella AI
      </p>
      <p className="leading-6 text-pretty whitespace-pre-line">{answer.text}</p>
      {answer.items.length > 0 && (
        <button type="button" aria-pressed={shown} onClick={onShow} className={cn(chip, "self-start font-medium", shown && "bg-star/25 text-star-ink hover:bg-star/25")}>
          {shown ? "Shown on the graph" : "Show on the graph"}
        </button>
      )}
    </article>
  )
}
