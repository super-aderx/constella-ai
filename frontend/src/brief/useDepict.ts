import { useCallback, useEffect, useRef, useState } from "react"
import { DepictBusy, getDepict, refreshCard, startDepict } from "../api"
import type { CardKey, Depict, DepictCard, Filters } from "../types"

/** How long the filters must stay put before a scope's Brief is started: a run costs 8 model calls. */
export const DEBOUNCE_MS = 2000
/** How often the cards are read again while some are still waiting or being answered. */
export const POLL_MS = 2000

const TROUBLE = "Couldn't reach the brief. Retrying…"

const keyOf = ({ days, segment }: Filters) => `${days ?? ""}|${segment ?? ""}`

const unsettled = (depict: Depict) => depict.cards.some((c) => c.state === "waiting" || c.state === "answering")

/**
 * A card as the server sent it, keeping what has not changed of the one before. Every response
 * sends the cards again as new objects, and the app knows answers and proposals by identity: the
 * answer shown on the graph, and the proposals already saved as campaigns. An unchanged card is
 * kept whole. A card being answered again (by a refresh here or in another browser) still carries
 * its old answer, so that answer object is kept too.
 */
export function keepCard(before: DepictCard | undefined, card: DepictCard): DepictCard {
  if (!before || before.answered_at !== card.answered_at) return card
  if (before.state === card.state) return before
  return before.answer && card.answer ? { ...card, answer: before.answer } : card
}

/** The newer cards of a scope, each kept from the older ones where it can be (`keepCard`). */
function keep(before: Depict | undefined, after: Depict): Depict {
  if (!before) return after
  const old = new Map(before.cards.map((c) => [c.key, c]))
  return { ...after, cards: after.cards.map((c) => keepCard(old.get(c.key), c)) }
}

/**
 * The Brief of the scope the graph shows. It is started on the server once the filters have
 * settled (at once on page load), then read again every few seconds until every card is done,
 * whether or not the Brief tab is open. Every scope seen is kept, so coming back to one shows its
 * cards at once. A scope left behind is no longer read, but keeps running on the server.
 */
export function useDepict(filters: Filters) {
  const key = keyOf(filters)
  /** The latest cards of each scope seen, by scope key. */
  const [known, setKnown] = useState<Map<string, Depict>>(() => new Map())
  /** The last request for a scope failed: shown only while that scope is the current one. */
  const [trouble, setTrouble] = useState<{ key: string; message: string } | null>(null)
  /** The scope being read, readable after an await. */
  const current = useRef({ key, filters })
  /** Reads the current scope again soon: after a refresh, which unsettles a card. */
  const wake = useRef<(() => void) | null>(null)
  /** Whether the page has just loaded: the first scope is started without waiting. */
  const first = useRef(true)

  const store = useCallback((scopeKey: string, depict: Depict) => {
    setKnown((before) => new Map(before).set(scopeKey, keep(before.get(scopeKey), depict)))
  }, [])

  const { days, segment } = filters
  useEffect(() => {
    const scope = { days, segment }
    current.current = { key, filters: scope }
    let left = false
    let started = false
    let inFlight = false
    /** A refresh came in while a read was in flight: read once more after it, even if all looked settled. */
    let again = false
    let timer: ReturnType<typeof setTimeout> | undefined

    // Starting is sent once per scope that settles (POST); everything after it is a read (GET). A
    // start that failed is sent again, since nothing runs until one gets through.
    const tick = async () => {
      first.current = false
      inFlight = true
      again = false
      try {
        const depict = await (started ? getDepict(scope) : startDepict(scope))
        started = true
        // Kept even for a scope left behind, so coming back to it shows what it had.
        store(key, depict)
        if (left) return
        setTrouble(null)
        if (unsettled(depict) || again) timer = setTimeout(tick, POLL_MS)
      } catch {
        if (left) return
        setTrouble({ key, message: TROUBLE })
        timer = setTimeout(tick, POLL_MS)
      } finally {
        inFlight = false
      }
    }

    wake.current = () => {
      if (inFlight) again = true
      else if (started) {
        clearTimeout(timer)
        timer = setTimeout(tick, POLL_MS)
      }
    }
    timer = setTimeout(tick, first.current ? 0 : DEBOUNCE_MS)
    return () => {
      left = true
      clearTimeout(timer)
      wake.current = null
    }
  }, [key, days, segment, store])

  /**
   * Answers one card of the current scope again. The card shows as answering at once, and the
   * scope is read until it is done. Throws when the server could not be asked.
   */
  const refresh = useCallback(
    async (card: CardKey) => {
      const { key: scopeKey, filters: scope } = current.current
      const merge = (updated: DepictCard) =>
        setKnown((before) => {
          const depict = before.get(scopeKey)
          if (!depict) return before
          return new Map(before).set(scopeKey, { ...depict, cards: depict.cards.map((c) => (c.key === updated.key ? keepCard(c, updated) : c)) })
        })
      try {
        merge(await refreshCard(scope, card))
      } catch (error) {
        // Already being answered (by another browser, say): nothing to do but follow it.
        if (!(error instanceof DepictBusy)) throw error
        if (error.card) merge(error.card)
      }
      if (current.current.key === scopeKey) wake.current?.()
    },
    [],
  )

  return {
    depict: known.get(key) ?? null,
    trouble: trouble?.key === key ? trouble.message : null,
    refresh,
  }
}
