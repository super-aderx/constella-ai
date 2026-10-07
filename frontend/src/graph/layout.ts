import type { Item, Pair } from "../types"

/** 0…1 on both axes, so the canvas can map them onto whatever size it measures. */
export type Positions = Record<string, [x: number, y: number]>

const GOLDEN = Math.PI * (3 - Math.sqrt(5))

/**
 * Force-directed layout (Fruchterman–Reingold with a pull toward each community's centre), started
 * from one cluster per community so groups stay together. Deterministic: no Math.random.
 * `aspect` is the width / height it is solved for.
 */
export function forceLayout(items: Item[], pairs: Pair[], aspect = 1.5, iterations = 400): Positions {
  const n = items.length
  const k = Math.sqrt(aspect / n) * 0.9
  const index = new Map(items.map((item, i) => [item.name, i]))
  const maxLift = Math.max(...pairs.map((p) => p.lift))
  const clusters: number[][] = []
  items.forEach((item, i) => (clusters[item.community] ??= []).push(i))

  // Start: communities on an ellipse, each one a small spiral.
  const x = new Float64Array(n)
  const y = new Float64Array(n)
  clusters.forEach((members, c) => {
    const angle = (c / clusters.length) * Math.PI * 2 - Math.PI / 2
    members.forEach((i, j) => {
      const r = k * 0.6 * Math.sqrt(j)
      x[i] = aspect / 2 + Math.cos(angle) * aspect * 0.3 + Math.cos(j * GOLDEN + c) * r
      y[i] = 0.5 + Math.sin(angle) * 0.3 + Math.sin(j * GOLDEN + c) * r
    })
  })

  for (let it = 0; it < iterations; it++) {
    const dx = new Float64Array(n)
    const dy = new Float64Array(n)
    // Every product type pushes every other away.
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const ex = x[i] - x[j]
        const ey = y[i] - y[j]
        const f = (k * k) / (ex * ex + ey * ey || 1e-6)
        dx[i] += ex * f
        dy[i] += ey * f
        dx[j] -= ex * f
        dy[j] -= ey * f
      }
    }
    // Pairs pull together, harder the higher their lift.
    for (const p of pairs) {
      const a = index.get(p.a)!
      const b = index.get(p.b)!
      const ex = x[a] - x[b]
      const ey = y[a] - y[b]
      const f = (Math.hypot(ex, ey) / k) * (0.55 + 0.45 * Math.sqrt(p.lift / maxLift))
      dx[a] -= ex * f
      dy[a] -= ey * f
      dx[b] += ex * f
      dy[b] += ey * f
    }
    // Each community holds together.
    for (const members of clusters) {
      const cx = members.reduce((sum, i) => sum + x[i], 0) / members.length
      const cy = members.reduce((sum, i) => sum + y[i], 0) / members.length
      for (const i of members) {
        dx[i] += (cx - x[i]) * 0.35
        dy[i] += (cy - y[i]) * 0.35
      }
    }
    // A little gravity, then a step that shrinks as the layout cools.
    const temperature = aspect * 0.08 * (1 - it / iterations)
    for (let i = 0; i < n; i++) {
      dx[i] += (aspect / 2 - x[i]) * 0.12
      dy[i] += (0.5 - y[i]) * 0.12 * aspect
      const d = Math.hypot(dx[i], dy[i]) || 1
      const step = Math.min(d, temperature)
      x[i] += (dx[i] / d) * step
      y[i] += (dy[i] / d) * step
    }
  }

  const minX = Math.min(...x)
  const minY = Math.min(...y)
  const spanX = Math.max(...x) - minX || 1
  const spanY = Math.max(...y) - minY || 1
  return Object.fromEntries(items.map((item, i) => [item.name, [(x[i] - minX) / spanX, (y[i] - minY) / spanY]]))
}
