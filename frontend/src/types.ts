/** The shapes the API sends (backend/app). */

/** One product (an item_name) inside a product type. */
export interface Product {
  name: string
  orders: number
  revenue: number
}

/** A product type (the item_tag column). Its name is its id. */
export interface Item {
  name: string
  /** Index into `Network.communities`. `null`: it has no pair above chance, so no community. */
  community: number | null
  /** Baskets that include it. */
  orders: number
  revenue: number
  /** Its best-selling products. */
  products: Product[]
  /** One of the types that most often connect two others. */
  bridge: boolean
}

/** Two items bought on the same invoice. */
export interface Pair {
  a: string
  b: string
  coOrders: number
  /** How many times more often the pair shares a basket than chance predicts. */
  lift: number
}

export interface Network {
  items: Item[]
  pairs: Pair[]
  /** The baskets a pair must share to be in the network. Lower under a filter that leaves less data. */
  minCoOrders: number
  /** Community labels, by index. */
  communities: string[]
  /** Every customer (RFM) segment in the data, for the filter. */
  segments: string[]
}

/** What the network covers. `null` means no filter. */
export interface Filters {
  /** The last this many days of the data. */
  days: number | null
  segment: string | null
}

/** How the graph is drawn: plain, with its bridges picked out, or coloured by community. */
export type Mode = "default" | "bridge" | "community"

/** What a line's width shows: the pair's lift, or the baskets that hold both. */
export type Metric = "lift" | "coOrders"

/** A pair by its two item names. */
export type PairRef = Pick<Pair, "a" | "b">

/** A figure in an answer and the ledger entry it came from. */
export interface Figure {
  /** What it measures, e.g. "lift". */
  name: string
  value: number
  /** A ledger id, e.g. "L2". */
  source: string
}

/** One ledger entry: a tool the agent called, with what it asked and what came back. */
export interface ToolCall {
  /** "L1", "L2" … in the order the calls were made. */
  id: string
  tool: string
  args: Record<string, unknown>
  result: unknown
}

/** The agent's answer, with the items and pairs it names: what the graph highlights. */
export interface Answer {
  text: string
  items: string[]
  pairs: PairRef[]
  /** From the agent with tools (v2) only: the figures it states and the calls behind them. */
  figures?: Figure[]
  ledger?: ToolCall[]
  review?: Review
  /**
   * The scope the answer is about, or the two scopes it compares. The graph follows: it switches
   * to the first, and splits in two for a comparison.
   */
  views?: Filters[]
  /** A chart of the answer's data, when the scientist chose to add one. */
  chart?: Chart | null
  /** Questions to tap: the choices when the agent asks which thing is meant, or what to ask instead of something it declined. */
  options?: string[]
  /** The strategist's campaign, when the question asked for something to do. */
  strategy?: Strategy | null
}

/** Campaign options built on the analyst's findings: two or three that differ. */
export interface Strategy {
  /** What the options are and how they differ, with figures cited like the answer's. */
  text: string
  campaigns: Campaign[]
  figures: Figure[]
}

export interface Campaign {
  name: string
  /** "proven": its product types already sell together. "potential": a candidate the data suggests, to test. */
  basis: "proven" | "potential"
  /** The two or three product types it bundles. */
  items: string[]
  discount_percent: number
  /** A customer segment, or `null` for all customers. */
  audience: string | null
  /** The writer's slogans to choose from. Empty when the campaigns did not pass their check. */
  slogans: Slogan[]
  /** The figures it rests on, in a sentence. */
  reason: string
}

export interface Slogan {
  text: string
  /** For a pun on a sound: the swap, e.g. "芒 ≈ 忙". `null` for a slogan with no pun. */
  pun: string | null
}

/** A chart as a pointer at ledger data: the app draws it from that tool result. */
export interface Chart {
  type: "bar" | "pie" | "heatmap"
  title: string
  /** The ledger id of the result to draw. */
  source: string
  /** The field naming each row, or "pair" for rows with `a` and `b`. */
  label: string
  /** The numeric field to draw. */
  value: string
}

/** The reviewer's check of an answer against its tool results, before it was sent. */
export interface Review {
  passed: boolean
  /** What the first check caught, when the agent was sent back to fix its draft. */
  caught: string[]
  /** What is still wrong after the retry. */
  notes: string[]
}

/**
 * A step of a run, reported as it starts: a role taking its turn ("router", "analyst", "review",
 * "fix", "strategist", "strategy_review", "strategy_fix", "writer", "scientist"), or "tool" for a call a role makes.
 */
export interface Step {
  step: string
  /** For "tool": the call, as its ledger entry will have it. */
  id?: string
  tool?: string
  args?: Record<string, unknown>
  /** For "fix" and "strategy_fix": how many things the review sent back. */
  notes?: number
}

/** A question, the steps of its run so far, and its answer, once it arrives. */
export interface Turn {
  question: string
  steps?: Step[]
  answer?: Answer
}
