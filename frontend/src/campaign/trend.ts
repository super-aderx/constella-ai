import { fmt } from "../lib"
import type { SavedCampaign } from "../types"
import { today } from "./draft"

/*
 * A campaign's day-by-day results. There are no real campaign metrics yet, so the numbers are made
 * up here, the same every time for the same campaign, and the page always tags them as sample data.
 */

export type TrendMetric = "revenue" | "orders" | "bundle_uptake" | "conversion_rate"

/** The metrics in tab order. Rates are averaged over the days; counts and money are totalled. */
export const TREND_METRICS: { key: TrendMetric; label: string; format: (v: number) => string; summary: "sum" | "mean" }[] = [
  { key: "revenue", label: "Revenue", format: fmt.money, summary: "sum" },
  { key: "orders", label: "Orders", format: fmt.int, summary: "sum" },
  { key: "bundle_uptake", label: "Bundle uptake", format: fmt.int, summary: "sum" },
  { key: "conversion_rate", label: "Conversion rate", format: (v) => (v * 100).toFixed(1) + "%", summary: "mean" },
]

export interface TrendPoint {
  /** "YYYY-MM-DD", the browser's local date. */
  date: string
  revenue: number
  orders: number
  bundle_uptake: number
  /** A fraction, 0–1. */
  conversion_rate: number
}

/** The metric over the whole period: a total, or the average day for a rate. */
export function summarize(points: TrendPoint[], metric: TrendMetric) {
  const total = points.reduce((sum, p) => sum + p[metric], 0)
  const { summary } = TREND_METRICS.find((m) => m.key === metric)!
  return summary === "mean" ? total / (points.length || 1) : total
}

/** "2026-11-03" as a local Date. Built from its parts: `new Date("2026-11-03")` is UTC midnight. */
const local = (date: string) => {
  const [y, m, d] = date.split("-").map(Number)
  return new Date(y, m - 1, d)
}

const shortFormat = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" })

/** "2026-11-03" as "Nov 3". */
export const shortDate = (date: string) => shortFormat.format(local(date))

/** Every date from `from` to `to`, both included. Stepping the day of a local Date keeps DST shifts out of it. */
function days(from: string, to: string) {
  const start = local(from)
  const out: string[] = []
  for (let i = 0; ; i++) {
    const day = today(new Date(start.getFullYear(), start.getMonth(), start.getDate() + i))
    if (day > to) return out
    out.push(day)
  }
}

/**
 * The days a campaign has a trend for, or null when it was never live. Launching only stores the
 * campaign as no longer a draft: one launched ahead of its start date is scheduled, with nothing
 * to chart yet. So the trend starts on the first day the pilot or the campaign actually ran.
 */
export function trendRange(campaign: SavedCampaign, now = new Date()): { from: string; to: string } | null {
  const { status, launched_at, pilot } = campaign
  if (status === "draft" || status === "scheduled" || launched_at === null) return null
  const launched = today(new Date(launched_at))
  const began = pilot ? pilot.starts_on : campaign.starts_on
  const from = launched > began ? launched : began
  let to: string
  if (status === "ended") to = campaign.ended_at ? today(new Date(campaign.ended_at)) : campaign.ends_on
  else if (status === "cancelled") to = campaign.cancelled_at ? today(new Date(campaign.cancelled_at)) : from
  else {
    const day = today(now)
    to = day < campaign.ends_on ? day : campaign.ends_on
  }
  // Cancelled or ended before it ever went live.
  return to < from ? null : { from, to }
}

/** FNV-1a: a campaign id as a 32-bit seed. */
function hash(text: string) {
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 0x01000193)
  return h >>> 0
}

/** mulberry32: a small seeded generator, so the same campaign always gets the same numbers. */
function seeded(seed: number) {
  let a = seed
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/**
 * A campaign's trend, one point per day, oldest first; null when it has none.
 *
 * MOCK: shaped like the future `GET /api/campaigns/:id/trend` so that real data replaces this body
 * and nothing else. Until then the numbers are invented: a gentle ramp-up with daily noise, seeded
 * by the campaign id. Each day takes its draws in order from one stream, so the days already shown
 * keep their values when a new day is added.
 */
export async function fetchCampaignTrend(campaign: SavedCampaign, now = new Date()): Promise<TrendPoint[] | null> {
  const range = trendRange(campaign, now)
  if (!range) return null
  const random = seeded(hash(campaign.id))
  const between = (low: number, high: number) => low + random() * (high - low)
  const base = between(20, 80)
  const basket = between(30, 90)
  return days(range.from, range.to).map((date, i) => {
    const ramp = 0.45 + 0.55 * Math.min(1, (i + 1) / 7)
    const orders = Math.max(0, Math.round(base * ramp * between(0.8, 1.2)))
    return {
      date,
      revenue: Math.round(orders * basket * between(0.9, 1.1)),
      orders,
      bundle_uptake: Math.round(orders * between(0.15, 0.45)),
      // 1–8%: higher once the campaign has warmed up, never outside the range.
      conversion_rate: Math.min(0.08, Math.max(0.01, 0.01 + 0.06 * ramp * between(0.7, 1.15))),
    }
  })
}
