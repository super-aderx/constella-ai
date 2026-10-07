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

/** The agent's answer, with the items and pairs it names: what the graph highlights. */
export interface Answer {
  text: string
  items: string[]
  pairs: PairRef[]
}

/** A question and its answer, once it arrives. */
export interface Turn {
  question: string
  answer?: Answer
}
