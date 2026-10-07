import type { Pair } from "./types"

export const cn = (...classes: (string | false | null | undefined)[]) => classes.filter(Boolean).join(" ")

const integer = new Intl.NumberFormat("en-US")

/** Number formats: 1,902 · $48,210 · 3.10× */
export const fmt = {
  int: (v: number) => integer.format(Math.round(v)),
  money: (v: number) => "$" + integer.format(Math.round(v)),
  lift: (v: number) => v.toFixed(2) + "×",
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
