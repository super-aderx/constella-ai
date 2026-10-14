import { useEffect, useRef, useState, type FormEvent } from "react"
import { GenMark } from "../Brand"
import type { Answer, Turn } from "../types"
import { AnswerCard, Options } from "./AnswerCard"
import { Progress } from "./Progress"
import { nextSteps, STARTERS } from "./Suggestions"

interface ChatProps {
  turns: Turn[]
  /** Every product type in the data shown, for choosing one to set aside. */
  types: string[]
  /** The product types set aside: the assistant builds no campaign on them. */
  ignored: string[]
  /** Sets a type aside, or takes it back. */
  onIgnore: (type: string) => void
  /** The answer the graph is showing. */
  shown: Answer | null
  onSend: (question: string) => void
  onShow: (answer: Answer) => void
  onReset: () => void
}

/** The conversation with the agent: suggestions when empty, then questions and answers, and the composer. */
export function Chat({ turns, types, ignored, onIgnore, shown, onSend, onShow, onReset }: ChatProps) {
  const busy = turns.some((t) => !t.answer)
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" })
  }, [turns])

  return (
    <section aria-label="Assistant" className="flex min-h-0 flex-col">
      <header className="flex h-10 shrink-0 items-start justify-between px-1">
        <h1 className="inline-flex items-center gap-2 font-semibold">
          <GenMark size={18} />
          Assistant
        </h1>
        {turns.length > 0 && (
          <button type="button" onClick={onReset} disabled={busy} className="cursor-pointer text-[13px] font-medium text-ink-muted hover:text-ink disabled:opacity-50">
            New chat
          </button>
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {turns.length === 0 ? (
          <div className="px-1 pt-2">
            <h2 className="text-[26px] leading-tight font-bold tracking-[-0.03em]">Ask the stars, check the answer.</h2>
            <p className="mt-2 text-ink-muted">Ask about product types, pairs and groups. Each answer lights up on the graph.</p>
            <Options options={STARTERS} onPick={onSend} className="mt-6" />
          </div>
        ) : (
          <ol className="flex flex-col gap-3">
            {turns.map((turn, i) => (
              <li key={i} className="flex flex-col gap-3">
                <p className="max-w-[85%] self-end rounded-2xl rounded-br-md bg-field px-4 py-2">{turn.question}</p>
                {turn.answer ? (
                  <AnswerCard
                    answer={turn.answer}
                    // Only the latest answer offers what to ask next: the conversation has moved on from the others.
                    next={i === turns.length - 1 ? nextSteps(turn.answer, turn.question, ignored) : []}
                    shown={turn.answer === shown}
                    onShow={() => onShow(turn.answer!)}
                    onAsk={onSend}
                  />
                ) : (
                  <Progress steps={turn.steps ?? []} />
                )}
              </li>
            ))}
          </ol>
        )}
        <div ref={endRef} className="h-2" />
      </div>

      <Ignored types={types} ignored={ignored} onIgnore={onIgnore} />
      <Composer onSend={onSend} busy={busy} />
    </section>
  )
}

/**
 * The product types left out of campaigns: each can be taken back, and another added from the list.
 * The graph and questions of fact are not affected.
 */
function Ignored({ types, ignored, onIgnore }: Pick<ChatProps, "types" | "ignored" | "onIgnore">) {
  const left = types.filter((type) => !ignored.includes(type)).sort((a, b) => a.localeCompare(b))
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5 px-1 text-[12px] text-ink-muted">
      {ignored.length > 0 && <span>Left out of campaigns:</span>}
      {ignored.map((type) => (
        <button
          key={type}
          type="button"
          aria-label={`Allow ${type} in campaigns again`}
          onClick={() => onIgnore(type)}
          className="cursor-pointer rounded-full bg-field px-2 py-0.5 text-ink transition-colors hover:bg-line"
        >
          {type} <span aria-hidden>×</span>
        </button>
      ))}
      {/* Always on its first option: it is a menu of types to add, not a value. */}
      <select
        value=""
        aria-label="Leave a product type out of campaigns"
        onChange={(e) => e.target.value && onIgnore(e.target.value)}
        className="max-w-full cursor-pointer rounded-full bg-transparent py-0.5 font-medium hover:text-ink"
      >
        <option value="">{ignored.length > 0 ? "+ Add" : "Leave a product type out of campaigns"}</option>
        {left.map((type) => (
          <option key={type}>{type}</option>
        ))}
      </select>
    </div>
  )
}

/** Only the button sends; Enter adds a line. The field grows with its text. */
function Composer({ onSend, busy }: { onSend: (question: string) => void; busy: boolean }) {
  const [text, setText] = useState("")
  const ready = text.trim() !== "" && !busy
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!ready) return
    onSend(text.trim())
    setText("")
  }
  return (
    <form onSubmit={submit} className="mt-2 flex items-end gap-2 rounded-2xl bg-surface-raised p-2 shadow-pop focus-within:outline-2 focus-within:outline-focus">
      <textarea
        rows={1}
        value={text}
        placeholder="Ask about product types, pairs or groups"
        aria-label="Message Constella AI"
        onChange={(e) => setText(e.target.value)}
        className="max-h-32 min-h-10 min-w-0 flex-1 resize-none bg-transparent px-2 py-2 leading-6 outline-none [field-sizing:content] placeholder:text-ink-faint"
      />
      <button
        type="submit"
        disabled={!ready}
        aria-label="Send"
        className="size-10 shrink-0 cursor-pointer rounded-xl bg-action text-[18px] text-on-action transition-colors disabled:cursor-default disabled:bg-field disabled:text-ink-faint"
      >
        ↑
      </button>
    </form>
  )
}
