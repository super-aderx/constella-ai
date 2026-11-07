# Campaign from strategy — Requirements

Status: confirmed
Last updated: 2026-11-07

> **Changed 2026-11-07 (CAI-7):** proposals are not stored and conversion is not measured. FR14,
> AC16 and the conversion metric are dropped. A saved campaign keeps a copy of the AI proposal it
> came from instead of a link to a stored proposal (FR10, AC11).

## Problem

Constella AI's strategist already proposes campaigns in the chat. Each proposal has a name, product
types, a discount % and an audience segment, with a reason. Today those proposals are only text. To
act on one, the store team has to copy it somewhere by hand and fill in the rest: dates, counties
and a pilot. This feature turns a proposal into a saved, scheduled campaign, with an optional pilot,
in a single guided flow.

## Users

- **Store team member** (marketing / merchandising). This is a single store team using one shared
  app, with no login. Campaigns belong to the store, not to a person. No ownership or permissions
  in this release.

## Goals & success metrics

- **Functional check for this release:** after Save, the campaign and its pilot settings exist in the
  database with status `scheduled` and every value the user saw on the review step.

## Core user flows

### Flow 1: Save a proposed campaign with a pilot
1. The user asks the chat for a strategy. The answer shows one or more proposed campaigns.
2. Each proposed campaign has an **"Add as campaign"** button. The user clicks it on one proposal.
3. A centered modal opens on **Step 1: Campaign**, prefilled from that proposal:
   - Title ← the proposal's name
   - Strategy ← the proposal's reasoning (editable free text)
   - Products ← the proposal's product types
   - Discount % ← the proposal's discount
   - Customer segment ← the proposal's audience (empty if it has none)
   - Start/end dates: empty
   - Counties: empty
4. The user adjusts fields. Products is a list with fuzzy search over product types and individual
   products (SKUs). The user can add or remove either kind.
5. The user clicks **Next** to go to **Step 2: Pilot**. The user turns on "Run a pilot first" and
   enters the pilot size (% of the target audience), pilot start/end dates and pilot discount %.
   The user then sets the toggle **"When the pilot passes: start the campaign automatically"**
   (on) or **"hold for my approval"** (off).
6. The user clicks **Next** to go to **Step 3: Review**. This is a read-only summary of every
   campaign and pilot setting.
7. The user clicks **Save**. The modal closes, a "Campaign saved" confirmation appears, and the
   proposal's button changes to **"Saved ✓"**.

### Flow 2: Save without a pilot
Same as Flow 1, except "Run a pilot first" stays off in Step 2. The review step shows "No pilot".

### Flow 3: Go back and edit
From Step 2 or Step 3, **Back** returns to the previous step with every entered value kept.

### Flow 4: Abandon
Closing the modal (X, Esc or a click outside) with any change asks "Discard this campaign draft?".
Confirming discards it, and nothing is saved. Cancelling returns to the modal unchanged.

### Flow 5: Save the same proposal again
Clicking "Saved ✓" reopens the modal, prefilled from the proposal again. On Save, a warning says
"You already saved a campaign from this proposal. Save another?". Confirming creates a second
campaign.

## Functional requirements

- FR1: Each proposed campaign in a strategy answer shows an "Add as campaign" button.
- FR2: The button opens a centered modal with three steps (Campaign → Pilot → Review), with Next and
  Back, and a visible indication of the current step.
- FR3: Step 1 fields:
  - Title: required
  - Strategy: free text, required
  - Products: required, at least one product type or SKU
  - Discount %: required, whole number 1–100
  - Start date and end date: required
  - Customer segment: optional, one of the existing segments; empty means all customers
  - Counties: optional, any number; empty means all counties
- FR4: Step 1 is prefilled from the clicked proposal: title, strategy, product types, discount and
  segment. Dates and counties start empty.
- FR5: The products field searches product types and SKUs with fuzzy matching (tolerates typos and
  partial words), shows selected items as a removable list, and marks each item as a type or a SKU.
- FR6: Step 2 has a "Run a pilot first" switch, off by default. When it is on, these fields are
  required:
  - Pilot size: % of the campaign's target audience, whole number 1–99
  - Pilot start date and end date
  - Pilot discount %: whole number 1–100
  - Auto-start toggle: on = start the campaign automatically when the pilot passes,
    off = hold for approval; default off
- FR7: Date rules:
  - End date must not be before start date, for both campaign and pilot.
  - Campaign and pilot start dates must not be in the past.
  - The pilot must end before the campaign starts.
- FR8: Next is blocked while the current step has invalid or missing fields. Each problem is shown
  next to its field.
- FR9: Step 3 shows every value from Steps 1–2 read-only, plus Back and Save.
- FR10: Save stores the campaign with status `scheduled`, together with all of its fields and its
  pilot settings (or "no pilot"), and keeps a copy of the AI proposal it came from.
- FR11: After a successful save, the modal closes, a "Campaign saved" confirmation appears, and the
  proposal's button reads "Saved ✓".
- FR12: Closing the modal with unsaved changes asks for confirmation (Flow 4). Closing without
  changes just closes it.
- FR13: Saving again from a proposal that was already saved shows a warning first. Confirming
  creates a new, separate campaign (Flow 5).

## Out of scope

- Anything after Save: running the pilot, judging whether it passed, auto-starting or approving the
  campaign, and sending offers to customers. This is the next proposal.
- Defining pilot pass criteria.
- A campaigns list, editing or deleting saved campaigns.
- The AI proposing dates, counties or pilot settings.
- Logins, per-user ownership and permissions.
- Picking individual named customers. Only segments are supported.

## Edge cases & error handling

- **Proposal without a segment:** the segment field starts empty, meaning all customers.
- **Proposed product type no longer exists in the catalog:** it is shown as removable and flagged
  "not found", and the user must remove it before Next.
- **Fuzzy search with no matches:** shows "No products match '<query>'".
- **Save fails** (network or server): the modal stays on Review with all values kept, shows an error
  message and lets the user retry. The button does not change to "Saved ✓".
- **Double-click on Save:** creates only one campaign.
- **Pilot switch turned off after its fields were filled:** the pilot values are not saved. The
  review step shows "No pilot".
- **Campaign dates changed after the pilot was set,** so the pilot now ends on or after the campaign
  start: Step 2 shows the error when the user returns to it, and Save is blocked until it is fixed.
- **Page reload:** "Saved ✓" markers may reset. The database is the source of truth.

## Constraints

- Lives in the existing constella-ai app (repo `constella-ai` only), in the existing chat.
- Saved campaigns must be inspectable in the database. The user will verify rows directly.

## Acceptance criteria

- AC1 (FR1): Given a strategy answer with 2 proposed campaigns, when it renders, then each proposal
  has its own "Add as campaign" button.
- AC2 (FR2, FR4): Given a proposal "Tea time bundle" with product types [teapot, tea cups], 15% and
  segment "Wholesale", when the user clicks its button, then a centered modal opens on Step 1 with:
  - title "Tea time bundle"
  - strategy = the proposal's reasoning
  - products = teapot and tea cups (as types)
  - discount 15
  - segment Wholesale
  - empty dates and counties
- AC3 (FR5): Given Step 1 is open, when the user types "teapto", then matching product types and SKUs
  containing "teapot" appear, each labelled type or SKU. Selecting one adds it to the list, and
  its × removes it.
- AC4 (FR3, FR8): Given Step 1 with no start date, when the user clicks Next, then they stay on Step 1
  and the date field shows a "required" error.
- AC5 (FR3): Given discount 0 or 101 or 12.5, when the user clicks Next, then a discount error is
  shown and Next is blocked. Given 100, Next is allowed.
- AC6 (FR6): Given Step 2 with the pilot switch off, when the user clicks Next, then Review shows
  "No pilot".
- AC7 (FR6, FR8): Given the pilot switch is on and pilot size is 100, when the user clicks Next, then a
  size error is shown (allowed 1–99).
- AC8 (FR7): Given campaign start 2026-12-01 and pilot end 2026-12-01, when the user clicks Next on
  Step 2, then the error "Pilot must end before the campaign starts" is shown.
- AC9 (FR2): Given the user is on Step 3, when they click Back twice, then they are on Step 1 with
  every value they entered unchanged.
- AC10 (FR9): Given valid Steps 1–2, when Step 3 opens, then every campaign and pilot field is shown
  with the entered value, including the auto-start choice in words.
- AC11 (FR10, FR11): Given a valid Review, when the user clicks Save, then one campaign row exists
  in the database with status `scheduled`. It has the same title, strategy, products (types and
  SKUs), discount, dates, segment, counties and pilot settings (or no pilot), and it keeps a copy
  of the AI proposal it came from. The modal also closes, "Campaign saved" shows, and the button reads
  "Saved ✓".
- AC12 (FR12): Given Step 1 with an edited title, when the user presses Esc, then "Discard this
  campaign draft?" appears. Confirming closes without saving, and cancelling keeps the modal and
  its values.
- AC13 (FR13): Given a proposal already saved once, when the user saves it again, then a warning
  appears first, and confirming creates a second, separate campaign row.
- AC14 (Edge): Given the save request fails, when the user clicks Save, then the modal stays on
  Review with values kept and an error shown, and no "Saved ✓" appears.
- AC15 (Edge): Given the user double-clicks Save, then exactly one campaign is stored.

## Assumptions (accepted by user)

- The button is on each proposed campaign, not one per answer.
- Products can be product types and/or individual SKUs.
- The discount is a percentage off: whole number, 1–100%, for both campaign and pilot.
- Targeting is one optional customer segment plus optional counties.
- Pilot size is a % of the campaign's target audience.
- The pilot is optional, and it must end before the campaign starts.
- Pilot pass criteria are deferred to the next proposal. Only the auto-start/hold choice is
  stored now.
- One store team, no login.
- After Save: the modal closes, a confirmation appears, and the button reads "Saved ✓". There is
  no campaigns list.
- Closing with changes asks to discard. Re-saving a proposal warns first.
- Dates, counties and pilot settings start empty, and the AI does not propose them.
- The saved status is `scheduled`.

- Pilot size 1–99% (100% would not be a pilot).
- The auto-start toggle defaults to **off** (hold for approval), the safer default.
- Dates are whole days (no time of day). The campaign and pilot start must be today or later.
- Strategy text and title are required.
- Product types the user has marked "ignored" in the chat can still be picked here.
- The "Saved ✓" marker on a proposal only lasts for the current page session.

## Open questions

- None blocking.

## Notes for tech plan

- The strategist's existing proposal shape (name, basis, product types, discount, audience,
  reason) is the prefill source. A saved campaign keeps a copy of the proposal as shown, so what
  the AI proposed can be compared with what the team saved. Proposals are not stored on their own.
- The database is currently read-only for the invoice data. Saved campaigns need writable storage.
- Counties and SKUs for search should come from the same data the app already reads, so the
  options match the store's data.
