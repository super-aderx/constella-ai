import type { Answer, Filters, Network } from "./types"

/** The backend's two endpoints. Vite proxies /api to it (see vite.config.ts). */

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

/** Asks the agent about the network the filters show. */
export const ask = (question: string, filters: Filters) =>
  request<Answer>("/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, ...filters }) })
