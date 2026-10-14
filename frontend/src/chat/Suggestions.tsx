import type { Answer } from "../types"

/** Where to start: one question for each thing the assistant can do. */
export const STARTERS = [
  "What are the top 5 product types by revenue?",
  "Which two product types are bought together most often?",
  "Which groups of product types exist?",
  "Which combinations have potential to grow?",
  "Suggest a campaign for the pair with the highest lift",
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
        `What else is bought with ${pair.a}?`,
        `Which sets of three product types include ${pair.a}?`,
        `Which combinations with ${pair.a} have potential to grow?`,
        `Suggest a campaign for ${pair.a} and ${pair.b}`,
      ]
    : [
        `What is bought with ${item} most often?`,
        `Which products sell best in ${item}?`,
        `Which combinations with ${item} have potential to grow?`,
        `Suggest a campaign around ${item}`,
      ]
  // Nor the question just asked.
  return (answer.strategy ? steps.slice(0, -1) : steps).filter((question) => question !== asked).slice(0, 3)
}
