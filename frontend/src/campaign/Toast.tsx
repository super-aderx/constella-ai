import { useEffect } from "react"

/** How long a toast stays. */
const SHOWN_MS = 4000

/**
 * A short message at the foot of the page that goes away on its own. The status region is always
 * there, so a screen reader announces the message when it is put in.
 */
export function Toast({ message, onDone }: { message: string | null; onDone: () => void }) {
  useEffect(() => {
    if (!message) return
    const timer = setTimeout(onDone, SHOWN_MS)
    return () => clearTimeout(timer)
  }, [message, onDone])
  return (
    <div role="status" className="pointer-events-none fixed bottom-6 left-1/2 z-20 -translate-x-1/2">
      {message && <p className="rounded-full bg-action px-4 py-2 text-[14px] font-medium text-on-action shadow-pop">{message}</p>}
    </div>
  )
}
