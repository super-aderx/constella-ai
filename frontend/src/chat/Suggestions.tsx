import type { Answer } from "../types"

/** Where to start: one question for each thing the assistant can do, in Chinese, as the users work. */
export const STARTERS = [
  "依營收排名前 5 的商品類型是哪些？",
  "哪兩種商品類型最常被一起購買？",
  "有哪些商品類型分組？",
  "哪些組合有成長潛力？",
  "為提升度最高的組合推薦一個行銷活動",
]

/**
 * What to ask after an answer, built from the product types and pairs it names: a closer look, where
 * it could grow, and something to do with it. Each question names its subject in full, since a
 * question is asked on its own, without the conversation before it. None for an answer that names
 * nothing, or that asks the user which thing they mean: its options are the next step. A product
 * type the user has set aside is not suggested.
 */
export function nextSteps(answer: Answer, asked: string, ignored: string[]): string[] {
  if (answer.options?.length) return []
  const pair = answer.pairs.find((p) => !ignored.includes(p.a) && !ignored.includes(p.b))
  const item = pair?.a ?? answer.items.find((name) => !ignored.includes(name))
  if (!item) return []
  // The campaign is last: with campaigns already drafted, the next step is not another one.
  const steps = pair
    ? [
        `還有哪些商品類型常與 ${pair.a} 一起購買？`,
        `哪些三種商品類型的組合包含 ${pair.a}？`,
        `哪些包含 ${pair.a} 的組合有成長潛力？`,
        `為 ${pair.a} 和 ${pair.b} 推薦一個行銷活動`,
      ]
    : [
        `哪些商品類型最常與 ${item} 一起購買？`,
        `${item} 中哪些商品賣得最好？`,
        `哪些包含 ${item} 的組合有成長潛力？`,
        `針對 ${item} 推薦一個行銷活動`,
      ]
  // Nor the question just asked.
  return (answer.strategy ? steps.slice(0, -1) : steps).filter((question) => question !== asked).slice(0, 3)
}
