import type { ReactNode } from "react"
import type { PilotDraft, ProductRef } from "../types"
import { formatDate, type WizardDraft } from "./draft"

/** "Dec 1, 2026 – Dec 31, 2026". */
export const dates = (start: string, end: string) => `${formatDate(start)} – ${formatDate(end)}`

/** One labelled value, in the review and in a saved campaign's detail. */
export function Row({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-3 border-t border-line py-2 first:border-t-0">
      <dt className="text-[12px] font-medium text-ink-muted">{term}</dt>
      <dd className="text-[14px] break-words">{children}</dd>
    </div>
  )
}

/** A campaign's products, each marked as a whole type or a single product. */
export function Products({ products }: { products: ProductRef[] }) {
  return (
    <ul>
      {products.map((product) => (
        <li key={`${product.kind}|${product.name}`}>
          {product.name} <span className="text-[12px] text-ink-muted">{product.kind === "type" ? "Type" : "Product"}</span>
        </li>
      ))}
    </ul>
  )
}

/** A pilot in words. */
export function Pilot({ pilot }: { pilot: PilotDraft }) {
  return (
    <ul>
      <li>{pilot.audience_percent}% of the audience</li>
      <li>{dates(pilot.starts_on, pilot.ends_on)}</li>
      <li>{pilot.discount_percent}% off</li>
      <li>{pilot.auto_start ? "When the pilot passes: start the campaign automatically" : "Hold for my approval when the pilot passes"}</li>
    </ul>
  )
}

/** Step 3: every value from steps 1 and 2, read-only and in words, and why the last save failed, if it did. */
export function ReviewStep({ draft, error }: { draft: WizardDraft; error: string | null }) {
  return (
    <div className="flex flex-col gap-3">
      <dl>
        <Row term="Title">{draft.title.trim()}</Row>
        <Row term="Strategy">
          <span className="whitespace-pre-line">{draft.strategy.trim()}</span>
        </Row>
        <Row term="Slogan">{draft.slogan.trim() || "No slogan"}</Row>
        <Row term="Products">
          <Products products={draft.products} />
        </Row>
        <Row term="Discount">{draft.discount_percent}% off</Row>
        <Row term="Dates">{dates(draft.starts_on, draft.ends_on)}</Row>
        <Row term="Customers">{draft.segment ?? "All customers"}</Row>
        <Row term="Counties">{draft.counties.length === 0 ? "All counties" : draft.counties.join(", ")}</Row>
        <Row term="Pilot">{draft.pilotOn ? <Pilot pilot={draft.pilot} /> : "No pilot"}</Row>
      </dl>
      {error && (
        <p role="alert" className="rounded-lg bg-star/15 px-3 py-2 text-[13px] text-star-ink">
          {error}
        </p>
      )}
    </div>
  )
}
