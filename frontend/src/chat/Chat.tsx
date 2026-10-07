import { useEffect, useRef, useState, type FormEvent } from "react"
import { GenMark } from "../Brand"
import type { Answer, Turn } from "../types"
import { AnswerCard, Options } from "./AnswerCard"

/** From the plan's golden questions: the ones the network alone can answer. */
const SUGGESTIONS = [
  "What are the top 5 product types by revenue?",
  "Which two product types are bought together most often?",
  "Which pair has the highest lift?",
  "Which groups of product types exist?",
]

interface ChatProps {
  turns: Turn[]
  /** The answer the graph is showing. */
  shown: Answer | null
  onSend: (question: string) => void
  onShow: (answer: Answer) => void
  onReset: () => void
}

/** The conversation with the agent: suggestions when empty, then questions and answers, and the composer. */
export function Chat({ turns, shown, onSend, onShow, onReset }: ChatProps) {
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
            <Options options={SUGGESTIONS} onPick={onSend} className="mt-6" />
          </div>
        ) : (
          <ol className="flex flex-col gap-3">
            {turns.map((turn, i) => (
              <li key={i} className="flex flex-col gap-3">
                <p className="max-w-[85%] self-end rounded-2xl rounded-br-md bg-field px-4 py-2">{turn.question}</p>
                {turn.answer ? (
                  <AnswerCard answer={turn.answer} shown={turn.answer === shown} onShow={() => onShow(turn.answer!)} />
                ) : (
                  <div aria-live="polite" className="flex flex-col gap-2 rounded-xl bg-surface-raised p-4">
                    <span className="text-[13px] text-ink-muted">Reading the data…</span>
                    {[92, 78, 54].map((w) => (
                      <span key={w} className="h-3 animate-pulse rounded-sm bg-field" style={{ width: `${w}%` }} />
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
        <div ref={endRef} className="h-2" />
      </div>

      <Composer onSend={onSend} busy={busy} />
    </section>
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
