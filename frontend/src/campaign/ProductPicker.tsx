import { useEffect, useState, type KeyboardEvent } from "react"
import { searchProducts } from "../api"
import { chip, cn } from "../lib"
import type { ProductHit, ProductRef } from "../types"
import { input, problem, type FieldControl } from "./Field"
import type { FieldErrors } from "./draft"

/** Wait this long after the last key before searching, so a word being typed is searched once. */
const DEBOUNCE_MS = 200

const KIND = { type: "Type", product: "Product" } as const

const same = (a: ProductRef, b: ProductRef) => a.kind === b.kind && a.name === b.name

interface ProductPickerProps {
  control: FieldControl
  value: ProductRef[]
  /** The step's problems: a "products.<i>" one marks that chip. */
  errors: FieldErrors
  onChange: (products: ProductRef[]) => void
}

type Search = { state: "idle" } | { state: "searching" } | { state: "failed" } | { state: "done"; hits: ProductHit[] }

/**
 * Product types and products found by what is typed (typos allowed, matched on the server), and
 * the chosen ones as removable chips. A combobox: ↑/↓ pick a hit, Enter adds it, Escape closes the
 * list without closing the wizard.
 */
export function ProductPicker({ control, value, errors, onChange }: ProductPickerProps) {
  const [query, setQuery] = useState("")
  const [search, setSearch] = useState<Search>({ state: "idle" })
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const listId = `${control.id}-hits`
  const q = query.trim()

  useEffect(() => {
    if (!q) {
      setSearch({ state: "idle" })
      return
    }
    // The last query's hits go at once, not when the wait is over: Enter must never add one of them.
    setSearch({ state: "searching" })
    // Each new query aborts the one before, so a slow answer to an old query never replaces a newer one.
    const aborter = new AbortController()
    const timer = setTimeout(() => {
      searchProducts(q, aborter.signal).then(
        (hits) => {
          setSearch({ state: "done", hits })
          setActive(0)
        },
        () => aborter.signal.aborted || setSearch({ state: "failed" }),
      )
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      aborter.abort()
    }
  }, [q])

  // Hits already chosen are left out: adding one twice is never what is meant.
  const hits = search.state === "done" ? search.hits.filter((hit) => !value.some((chosen) => same(chosen, hit))) : []
  const listed = open && q !== "" && search.state !== "idle"

  // The input keeps the focus, so the list does not scroll by itself to the hit the arrows pick.
  useEffect(() => {
    if (listed) document.getElementById(`${listId}-${active}`)?.scrollIntoView({ block: "nearest" })
  }, [listed, listId, active, hits.length])

  const add = (hit: ProductHit) => {
    onChange([...value, { kind: hit.kind, name: hit.name }])
    setQuery("")
  }

  const keys = (e: KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault()
      setOpen(true)
      if (hits.length > 0) setActive((i) => (i + (e.key === "ArrowDown" ? 1 : hits.length - 1)) % hits.length)
    } else if (e.key === "Enter") {
      e.preventDefault()
      if (listed && hits[active]) add(hits[active])
    } else if (e.key === "Escape" && listed) {
      // The list closes, not the wizard around it.
      e.preventDefault()
      e.stopPropagation()
      setOpen(false)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {value.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {value.map((product, i) => {
            const error = errors[`products.${i}`]
            return (
              <li key={`${product.kind}|${product.name}`} className="flex flex-col gap-0.5">
                <span className={cn(chip, "inline-flex cursor-default items-center gap-1.5 py-1 hover:bg-field", error && "ring-2 ring-star")}>
                  {product.name}
                  <span className="text-[11px] text-ink-muted">{KIND[product.kind]}</span>
                  <button
                    type="button"
                    aria-label={`Remove ${product.name}`}
                    onClick={() => onChange(value.filter((_, j) => j !== i))}
                    className="cursor-pointer px-0.5 leading-none text-ink-muted hover:text-ink"
                  >
                    ×
                  </button>
                </span>
                {error && <span className={problem}>{error}</span>}
              </li>
            )
          })}
        </ul>
      )}
      <div className="relative">
        <input
          {...control}
          role="combobox"
          aria-expanded={listed}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={listed && hits[active] ? `${listId}-${active}` : undefined}
          value={query}
          placeholder="Search product types and products"
          autoComplete="off"
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={keys}
          className={input}
        />
        {listed && (
          <ul id={listId} role="listbox" aria-label="Matching products" className="absolute top-full right-0 left-0 z-10 mt-1 max-h-56 overflow-y-auto rounded-lg border border-line bg-surface-raised py-1 text-[14px] shadow-pop">
            {search.state === "searching" && <li className="px-2.5 py-1.5 text-ink-muted">Searching…</li>}
            {search.state === "failed" && <li className={cn(problem, "px-2.5 py-1.5")}>Search failed. Try again.</li>}
            {search.state === "done" && hits.length === 0 && <li className="px-2.5 py-1.5 text-ink-muted">No products match '{q}'</li>}
            {hits.map((hit, i) => (
              <li
                key={`${hit.kind}|${hit.name}`}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                // Keeps the focus in the field, so the list is not closed by its blur before the click lands.
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setActive(i)}
                onClick={() => add(hit)}
                className={cn("flex cursor-pointer items-baseline justify-between gap-3 px-2.5 py-1.5", i === active && "bg-field")}
              >
                <span>{hit.name}</span>
                <span className="shrink-0 text-[11px] text-ink-muted">{hit.kind === "type" ? KIND.type : `${KIND.product} · ${hit.type}`}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
