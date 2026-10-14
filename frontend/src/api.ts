import type { Answer, Filters, Network, Step } from "./types"

/** The backend's endpoints. Vite proxies /api to it (see vite.config.ts). */

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init)
  if (!response.ok) throw new Error(`The API answered ${response.status} for ${path}. Is the backend running?`)
  return response.json()
}

const networks = new Map<string, Promise<Network>>()

/** The network for one filter. Each filter is fetched once, so the same promise can be read on every render. */
export function getNetwork({ days, segment }: Filters) {
  const query = new URLSearchParams()
  if (days) query.set("days", String(days))
  if (segment) query.set("segment", segment)
  const path = `/network?${query}`
  if (!networks.has(path)) networks.set(path, request<Network>(path))
  return networks.get(path)!
}

/**
 * Asks the agent about the network the filters show. `ignored` are the product types it must build
 * no campaign on. The answer comes as a stream of JSON lines: each step of the run as it starts,
 * passed to `onStep`, then the answer.
 */
export async function ask(question: string, filters: Filters, ignored: string[], onStep: (step: Step) => void): Promise<Answer> {
  const path = "/ask/stream"
  const response = await fetch(`/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, ...filters, ignored }) })
  if (!response.ok || !response.body) throw new Error(`The API answered ${response.status} for ${path}. Is the backend running?`)
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  // A chunk can end mid-line: the unfinished part waits for the next one.
  let rest = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    const lines = (rest + value).split("\n")
    rest = lines.pop()!
    for (const line of lines.filter(Boolean)) {
      const event: Step | { answer: Answer } | { error: string } = JSON.parse(line)
      if ("step" in event) onStep(event)
      else if ("answer" in event) return event.answer
      else throw new Error(event.error)
    }
  }
  throw new Error("The answer was cut off before it arrived. Is the backend running?")
}
