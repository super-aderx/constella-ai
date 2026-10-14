import type { Pair } from "./types"

export const cn = (...classes: (string | false | null | undefined)[]) => classes.filter(Boolean).join(" ")

const integer = new Intl.NumberFormat("en-US")

/** Number formats: 1,902 · $48,210 · 3.10× */
export const fmt = {
  int: (v: number) => integer.format(Math.round(v)),
  money: (v: number) => "$" + integer.format(Math.round(v)),
  lift: (v: number) => v.toFixed(2) + "×",
}

/** A tool call as written: top_pairs(by="lift", limit=8). Filters left empty are not shown. */
export function callText(tool: string, args: Record<string, unknown>) {
  const shown = Object.entries(args).filter(([, value]) => value != null)
  return `${tool}(${shown.map(([name, value]) => `${name}=${JSON.stringify(value)}`).join(", ")})`
}

const RANKED: Record<string, string> = { co_orders: "shared baskets", lift: "lift", revenue: "revenue", orders: "orders" }

/** What each tool looks up, in a few words. */
const LOOKUPS: Record<string, (args: Record<string, unknown>) => string> = {
  find_item: (a) => `Which product type “${a.text}” means`,
  top_items: (a) => `Top ${a.limit} product types by ${RANKED[String(a.by)]}`,
  top_pairs: (a) => `Top ${a.limit} pairs by ${RANKED[String(a.by)]}`,
  item_neighbors: (a) => `What is bought with ${a.item}, by ${RANKED[String(a.by)]}`,
  pair_stats: (a) => `How often ${a.a} + ${a.b} are bought together`,
  central_items: (a) => `Top ${a.limit} bridges between product types`,
  communities: () => "Groups of product types bought together",
  item_products: (a) => `Best-selling products in ${a.item}`,
  top_bundles: (a) => `Top ${a.limit} sets of three${a.item ? ` with ${a.item}` : ""} by ${RANKED[String(a.by)]}`,
  potential_pairs: (a) => `Pairs with room to grow${a.item ? ` with ${a.item}` : ""}, by ${a.method === "segment_gap" ? "segment gap" : "shared partners"}`,
}

/** A scope a tool was asked about, when it is not all of the data: "忠誠客戶, last 90 days". */
const scopeText = (scope: Record<string, unknown>) => [scope.segment, scope.days && `last ${scope.days} days`].filter(Boolean).join(", ")

/** A tool call in plain words, on one line: "Top 8 pairs by lift · last 90 days". A tool not listed is shown as written. */
export function callSummary(tool: string, args: Record<string, unknown>) {
  if (tool === "compare") {
    const [a, b] = [args.a, args.b].map((side) => scopeText((side ?? {}) as Record<string, unknown>) || "all of the data")
    return `What differs between ${a} and ${b}`
  }
  const lookup = LOOKUPS[tool]
  if (!lookup) return callText(tool, args)
  const scope = scopeText(args)
  return scope ? `${lookup(args)} · ${scope}` : lookup(args)
}

/** Whether a written number states a figure, allowing for rounding as the reviewer does (backend/app/roles/reviewer.py): 2.104 written as 2.10. */
export const close = (written: number, value: number) => Math.abs(written - value) <= Math.max(0.01, 0.005 * Math.abs(value))

/** A text cut at each number it writes (1234.5 or 1,234.5), each number with the figure it states, if any. */
export function citeParts<F extends { value: number }>(text: string, figures: F[]): { text: string; figure?: F }[] {
  // Splitting on a captured number puts the numbers at the odd places.
  return text.split(/(\d+(?:,\d{3})*(?:\.\d+)?)/).map((part, i) => {
    if (i % 2 === 0) return { text: part }
    const written = Number(part.replaceAll(",", ""))
    const figure = figures.filter((f) => close(written, f.value)).sort((x, y) => Math.abs(written - x.value) - Math.abs(written - y.value))[0]
    return { text: part, figure }
  })
}

/** One key for a pair, whichever way round it is named. */
export const pairKey = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`)

/** An item's partners, strongest lift first. */
export function partnersOf(pairs: Pair[], name: string) {
  return pairs
    .filter((p) => p.a === name || p.b === name)
    .map((p) => ({ name: p.a === name ? p.b : p.a, lift: p.lift, coOrders: p.coOrders }))
    .sort((x, y) => y.lift - x.lift)
}
