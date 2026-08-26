# Frontend PRD — BUSY Integration Platform Console

A React single-page application for tablets, generated with Figma Make, talking to the
fembin FastAPI backend at `https://busyapi.femtechaccess.com.ng`. Two surfaces in one app:
a **Sales Rep console** used by cashiers standing at branch counters to create Sale
Quotations that post into BUSY accounting, and an **Admin console** for the superadmin who
manages users, barcodes, WooCommerce publishing, and sync health.

This document is the complete build contract: screens, components, states, and the exact
API bindings. Field names are literal — they match the backend exactly.

---

## 1. Product overview

| | |
|---|---|
| Platform | React SPA, tablet-first (landscape), also usable on desktop |
| Primary color | Blue (palette below) |
| Users | Branch sales reps/cashiers (many, low-permission) + one superadmin |
| Core job | Build a quotation → submit → watch it post to BUSY → show the BUSY voucher number |
| Auth | JWT bearer token, 8-hour shift expiry, re-login on expiry (no refresh endpoint) |
| Currency | Nigerian Naira ₦, two decimal places |
| Language | English |

**Mental model reps must never have to learn:** submitting a quotation does not return a
receipt instantly. It enters a queue (`queued → running → done | failed`) because writes
go through an outbox worker into the customer's live BUSY accounting software. The UI must
make this queue visible and reassuring, and celebrate the final BUSY voucher number
(e.g. `RCC-42`) when it arrives.

---

## 2. Users & permissions

### 2.1 Personas

**Sales Rep ("cashier")** — stands at a branch counter on a tablet, serves customers
face-to-face. Needs speed, big touch targets, minimal typing. Sees ONLY their own branch's
data (the server derives their branch from their login — there is no branch switcher for
reps).

**Superadmin** — office-based owner/operator on the same tablet or a desktop. Full
visibility across all branches plus user management, barcode assignment, WooCommerce
publishing, and catalog-sync health.

### 2.2 Capability matrix (drives navigation visibility)

| Capability | Rep | Superadmin |
|---|---|---|
| Create quotations for own branch | ✅ | ✅ (branch = their own user's assignment) |
| View quotations for own branch | ✅ | ✅ |
| View quotations for ALL branches | ❌ | ✅ |
| Browse products/categories/sales people/branches | ✅ (read-only) | ✅ |
| Assign product barcodes | ❌ | ✅ |
| Push products to WooCommerce | ❌ | ✅ |
| Trigger catalog sync / view sync health | ❌ | ✅ (API itself is open; UI gates it) |
| Create users | ❌ | ✅ |

Role comes from `GET /auth/me` → `is_superadmin`. The shell renders nav accordingly;
the server enforces everything anyway (403s must be handled gracefully regardless).

---

## 3. Design system

### 3.1 Color

Primary blue ramp (Tailwind-style naming for the generator):

| Token | Hex | Use |
|---|---|---|
| `primary-50` | `#EFF6FF` | subtle backgrounds, selected row tint |
| `primary-100` | `#DBEAFE` | hover states, chip backgrounds |
| `primary-200` | `#BFDBFE` | borders on focused inputs |
| `primary-300` | `#93C5FD` | disabled accents |
| `primary-500` | `#3B82F6` | secondary buttons, links |
| `primary-600` | `#2563EB` | **primary buttons, active nav item, key CTAs** |
| `primary-700` | `#1D4ED8` | pressed state, headers, brand marks |
| `primary-900` | `#1E3A8A` | dark text on light-blue surfaces |

Neutrals: standard slate/gray ramp (`#F8FAFC` page background, `#0F172A` text).
Status colors (fixed semantic mapping — do not vary by screen):

| Status | Chip bg | Chip text | Meaning |
|---|---|---|---|
| `queued` | amber-100 `#FEF3C7` | amber-800 | accepted, waiting for worker |
| `running` | primary-100 | primary-700 | being posted to BUSY right now |
| `done` | green-100 `#DCFCE7` | green-800 | posted; voucher number available |
| `failed` | red-100 `#FEE2E2` | red-800 | attempts exhausted; show error + retry |
| Woo actions `created/updated/skipped/not_found/failed` | same green/blue/slate/amber/red family | | |

### 3.2 Layout & touch

- **Reference canvas: 1280×800 landscape** (typical Android tablet). Must degrade
  gracefully to 1024×768 and to portrait 800×1280 (nav collapses to icon rail or bottom
  bar).
- Minimum touch target **48×48 px**; comfortable is 56px for primary CTAs.
- Standing-use typography: base font 16px, table text ≥15px, headings bold and generous.
  A cashier glances at this screen mid-conversation.
- Sticky elements: top app bar always visible; on forms, the submit action sits in a
  sticky footer bar so it's reachable without scrolling.
- Numeric input for quantity opens a large custom numpad (0–9, ⌫, clear) — cashiers'
  fingers, not styluses.
- Motion: subtle only (150–200ms transitions). No decorative animation during the
  quotation-status flow except a gentle pulse on the `running` chip.

### 3.3 Component library (generate these once, reuse everywhere)

- `AppShell` — top bar (brand, screen title, connection/status area, user menu) + left nav rail (desktop/tablet-landscape) collapsing to bottom bar (portrait).
- `StatusChip(status)` — maps `queued/running/done/failed` per §3.1.
- `DataTable` — sortable columns, sticky header, zebra rows, row height ≥52px.
- `SearchInput` — debounced (300ms) text field with clear button; drives server-side `search=` params.
- `FilterChipRow` — horizontally scrollable category/filter chips.
- `Numpad` — modal numeric keypad returning a decimal string.
- `MoneyInput`, `QtyInput` — accept decimals, display ₦-formatted on blur, store raw string (see §8.4).
- `Modal`, `BottomSheet`(portrait), `Toast`(success/error/info, auto-dismiss 4s, error persists until dismissed).
- `EmptyState(illustration?, title, hint)` and `LoadingSkeleton(rows)`.
- `BranchBadge(name)` — small pill showing the signed-in user's material center name.
- `JobStatusTimeline` — horizontal stepper: Submitted → Queued → Posting to BUSY → Done (with voucher number) / Failed.
- `ConfirmDialog` — for destructive/irreversible actions.

---

## 4. Information architecture

```
Login (no auth)
└── AppShell (role-aware nav)
    ├── Rep + Superadmin both get:
    │   ├── New Quotation          ← default landing after login for reps
    │   └── My Quotations          ← own-branch list + detail
    ├── Superadmin only:
    │   ├── Dashboard              ← sync health + Woo stats at a glance
    │   ├── All Quotations         ← every branch
    │   ├── Users                  ← list + create
    │   ├── Products               ← catalog manager: barcode assign, Woo push
    │   ├── Sales People           ← read-only master incl. inactive toggle
    │   └── Branches               ← read-only reference list
    └── Future (render as disabled nav items with "coming soon" tooltip — do NOT design screens):
        ├── Loyalty
        ├── Credit Partners
        └── Payments
```

Reps land on **New Quotation**; superadmins land on **Dashboard**.

---

## 5. Screens — detailed specs

### 5.1 Login
- Fields: Username, Password (show/hide eye). Big "Sign in" button.
- Bind: `POST /auth/login` `{username, password}` → store `access_token` (localStorage key
  `fembin_token`) → immediately call `GET /auth/me`; stash the profile; route by role.
- 401 → inline form error "Invalid username or password." Network failure → toast.
- No registration, no password reset (backend has neither). Show support phone placeholder.

### 5.2 AppShell top bar
- Left: brand mark "Femtech · BUSY Console".
- Center: current screen title.
- Right: `BranchBadge` (from `/auth/me.material_center_name`), user avatar menu
  (full name, username, Sign out), and for admins a global "Sync" status dot
  (green/gray from latest `/sync/status` fetch).

### 5.3 New Quotation (the money screen — invest here)
Single-page builder, three zones:

**A. Header strip (always visible):** Date (defaults to today, editable, stored as
`DD-MM-YYYY`), Customer Name (free text — there is no customer master yet),
Sale Type (dropdown fed by app constant `SALE_TYPES = ["Repair"]`; free-text allowed via
"Other…"), Sales Person (required dropdown from `GET /sales-people`, shows `name`,
secondary line `alias` when present).

> Config constants shipped in the app bundle (company-specific, NOT user-editable):
> `VCH_SERIES_NAME = "Main"`, `VCH_NO_PREFIX = "RCC"`, `SALE_TYPES = ["Repair"]`.
> These mirror how the business configured BUSY. Render them in a hidden "Advanced"
> drawer for support debugging.

**B. Item lines builder:** left panel = catalog browser (`SearchInput` bound to
`GET /products?search=`, `FilterChipRow` of categories from `GET /categories`, default
filter `active=true`). Tap a product row → adds a line. Right panel = current lines table:
Name, Unit (from product, read-only), Qty (tap → Numpad), Price (pre-filled from
product.price, editable via Numpad), Amount (computed, read-only), remove button.
Below table: subtotal (sum of amounts), VAT row **placeholder only** (no VAT logic exists
in the API — render "VAT: —" grayed out), grand total = subtotal.

Adding the same product twice merges quantities. Lines can be reordered (drag handle) —
line order is preserved in the payload array.

**C. Sticky footer:** line count + grand total + primary CTA "Submit to BUSY".

On submit:
1. Client-side validation (§8.5); inline errors per field.
2. Generate `idempotency_key = crypto.randomUUID()`; keep it attached to this draft until
   submission definitively succeeds or fails (§8.2 retry semantics).
3. `POST /quotations` (full shape in §7.3) → expect **202** with the created job.
4. Navigate to Quotation Detail (§5.4) carrying the job `id`.

Edge errors: 409 → toast "Your assigned material center no longer exists — contact
admin." and block submission. 422 (sales person) → highlight the Sales Person dropdown
with "no longer active — pick another". 401 → session expired modal → re-login (draft
preserved in memory/localStorage so nothing is lost).

Draft persistence: autosave the draft to localStorage on every change; restore on next
visit; explicit "Discard draft" in overflow menu with ConfirmDialog.

### 5.4 Quotation Detail (status tracker)
- `GET /outbox/{job_id}` on load, then poll every 5s while status ∈ {queued, running};
  stop polling on terminal states. Also refresh silently if user pulls-to-refresh /
  revisits.
- `JobStatusTimeline` visualizes Submitted → Queued → Posting to BUSY → outcome.
- When `status="done"`: success banner "Posted to BUSY", receipt card showing
  `result.vch_no` in very large type (this is what gets shouted across the counter or
  written on paper for the customer), plus `vch_code`, submitted date, items table,
  totals, sales person, customer. Include a print-friendly layout (@media print hides
  chrome).
- When `status="failed"`: red banner with `last_error` verbatim in a mono block (these
  errors come from BUSY and support diagnoses from them), `attempts` count shown, and a
  **Retry** button → creates a NEW submission prefilled from `payload` but with a FRESH
  `idempotency_key` (never reuse the failed job's key — see §8.2).
- While `queued`: set expectation honestly — helper text "Usually posts within a minute.
  You can safely start another quotation."

### 5.5 My Quotations
- `GET /quotations` → own-branch jobs, newest first. Table columns: Date (from
  `payload.date`), Customer (`payload.customer_name`), Items count, Total (compute sum of
  `payload.items[].amount`), Status chip, Voucher № (`result.vch_no` or "—").
- Row tap → Quotation Detail. Search box filters client-side across customer/voucher no.
  Filter chips: All / Queued / Running / Done / Failed.
- No pagination exists in the API — render full list with windowed virtualization; fine
  for expected volumes (hundreds per branch).

### 5.6 Admin — Dashboard
Cards grid:
- **Catalog sync**: per-entity rows from `GET /sync/status.busy` → entity name,
  `last_stamp`, relative `updated_at` ("2m ago"), and a "Sync now" button
  (`POST /sync/products {full:false}`) + overflow "Full resync" (`{full:true}`) behind
  ConfirmDialog ("Re-pulls entire catalog from BUSY; slow").
- **WooCommerce**: `seeded` badge, `last_run_at`, and the five counters
  (`last_seeded/created/updated/skipped/failed`) as stat tiles.
- **At a glance**: counts computed client-side from `GET /admin/quotations` — today's
  quotes, done vs failed today, top branch by volume.

### 5.7 Admin — All Quotations
Same table as §5.5 plus a Branch column (`payload.material_center_name`). Filters: status
chips + branch dropdown (options from `GET /material-centers`). Row tap → read-only
detail view (same receipt card; no retry for other branches' jobs — viewing only).

### 5.8 Admin — Users
- Table from `GET /admin/users`: username, full name, branch
  (`material_center_code` resolved to name via `/material-centers`), active toggle
  (read-only display), superadmin badge, created date.
- "Add user" → modal: username, full name, password (+confirm), Material Center dropdown
  (active centers only, from `/material-centers`). Bind `POST /auth/users`.
  - 409 → "That username is taken."
  - 422 → "Material center doesn't match a known, active branch."
- NOTE (honest scope): the API has **no edit/deactivate/reset-password endpoints yet** —
  render rows read-only and put disabled Edit buttons with tooltip "Coming soon" rather
  than fake affordances.

### 5.9 Admin — Products
- `GET /products?search=&category=&active=` toolbar: SearchInput, category chips,
  Active/All toggle. Table: code, name, group, price, unit, barcode (or "—"), Woo status
  (dot: synced if `woo_product_id` present, price-mismatch warning icon if
  `woo_synced_price !== price`), active.
- Row tap → detail sheet: full fields + two admin actions:
  - **Assign barcode**: input (supports USB/keyboard-wedge scanners — they type +
    Enter). Bind `PUT /products/{code}/barcode {barcode}`. 409 → "Already assigned to
    another product." Success toast.
  - **Push to WooCommerce**: checkbox multi-select mode across the table → sticky bar
    "Push N selected" → `POST /sync/woocommerce/push {busy_codes:[...]}` → results
    dialog listing each item's `action` chip + error text. If API returns 409 (Woo not
    configured) → explanatory toast quoting the detail message.

### 5.10 Admin — Sales People
`GET /sales-people` for the picker view; admin screen uses `GET /admin/sales-people`
(includes inactive). Read-only table: name, alias, active chip, updated. Banner note:
"This list mirrors BUSY 'Engineer' records — manage names in BUSY, not here."

### 5.11 Admin — Branches
Read-only cards/table from `GET /material-centers`: name, alias, parent group, active.
No actions (centers are managed in BUSY).

---

## 6. Global behaviors

- **Session expiry**: any 401 → clear token → modal "Session expired — sign in again" →
  login. Preserve in-progress draft.
- **Offline / server unreachable**: amber banner under the top bar "Offline — changes
  can't be submitted"; disable Submit; drafts still autosave locally.
- **Every request**: `Authorization: Bearer <token>` (except login), `Content-Type:
  application/json`. Log response `X-Request-ID` to console for support escalation.
- **Errors**: non-2xx bodies are `{"detail": "<human message>"}` — surface `detail` in
  toasts/inline; never swallow. 422s may be FastAPI validation arrays — flatten to the
  first message.
- **Clock/dates**: send `DD-MM-YYYY` strings exactly (BUSY requirement). Never send ISO
  dates to the quotation endpoint.

---

## 7. API contract (exact)

Base URL: `https://busyapi.femtechaccess.com.ng/api/v1` (configurable via env var at
build time).

### 7.1 Endpoints ↔ screens

| Endpoint | Method | Used by | Purpose |
|---|---|---|---|
| `/auth/login` | POST | 5.1 | obtain token |
| `/auth/me` | POST-login bootstrap | all | profile + role + branch |
| `/auth/users` | POST | 5.8 | create user (superadmin) |
| `/products?search=&category=&active=` | GET | 5.3, 5.9 | catalog browse/search |
| `/products/{code}` | GET | 5.9 detail | single product |
| `/products/{code}/barcode` | PUT | 5.9 | assign barcode (superadmin) |
| `/categories` | GET | 5.3, 5.9 | filter chips |
| `/material-centers` | GET | 5.7, 5.8, 5.11 | branches |
| `/sales-people` | GET | 5.3 | engineer dropdown (active only) |
| `/sales-people` (admin variant) | GET `/admin/sales-people` | 5.10 | incl inactive |
| `/quotations` | POST | 5.3 | submit quotation → 202 job |
| `/quotations` | GET | 5.5 | own-branch jobs |
| `/outbox/{job_id}` | GET | 5.4 | poll job status |
| `/admin/users` | GET | 5.8 | all users |
| `/admin/quotations` | GET | 5.6, 5.7 | all-branch jobs |
| `/sync/products` | POST | 5.6 | trigger catalog sync |
| `/sync/status` | GET | 5.6 | checkpoints + Woo counters |
| `/sync/woocommerce/push` | POST | 5.9 | push selected products |

### 7.2 Types (literal field names)

```ts
type ProductOut = { busy_code:number; name:string; price:string; unit:string;
  item_group:string; tracks_stock:boolean; is_active:boolean;
  woo_product_id:number|null; woo_synced_price:string|null;
  barcode:string|null; updated_at:string };

type JobStatus = "queued"|"running"|"done"|"failed";

type OutboxJobOut = { id:number; job_type:"add_sale_quotation"; status:JobStatus;
  attempts:number; payload:Record<string,any>|null;
  result:{vch_code:number; vch_no:string}|null; last_error:string|null;
  created_at:string; updated_at:string };
```

Note `price`/`woo_synced_price` serialize as JSON strings (Decimal) — parse with care,
format with `Intl.NumberFormat("en-NG",{style:"currency",currency:"NGN"})`.

### 7.3 Quotation submission payload (exact)

```json
{
  "idempotency_key": "b1e0c6de-9f2a-4c77-9d3a-1f6f2ab3c9e1",
  "vch_series_name": "Main",
  "vch_no_prefix": "RCC",
  "date": "22-08-2026",
  "sale_type_name": "Repair",
  "customer_name": "Mrs. Adaeze Okafor",
  "sales_person_id": 1613,
  "items": [
    {"item_name": "Cable-infinix Micro/Typ C", "unit_name": "Pcs",
     "qty": "2", "price": "1500.00", "amount": "3000.00"}
  ]
}
```

Rules: `material_center_*` is NEVER sent (server derives from token). `qty`, `price`,
`amount` are strings; `amount = qty × price` computed client-side at 2dp; `price` defaults
from the product but is editable (counter discounts exist). Empty `items` blocks submit.

### 7.4 Response codes worth designing for

| Code | Where | UI |
|---|---|---|
| 401 | any authed call | session-expired modal |
| 403 | admin calls as rep | toast "Superadmin access required" (shouldn't happen; nav hides these) |
| 404 | product/outbox lookups | empty-state in place |
| 409 | duplicate username/barcode; missing branch; unconfigured Woo | specific messages above |
| 422 | validation (bad sales person etc.) | inline field errors |
| 202 | submissions/triggers | success + async tracking UX |

---

## 8. Business rules encoded in the UI

1. **Idempotent retries (§8.2)** — one UUID per logical submission. Network timeout/5xx on
   submit → offer "Try again" which re-sends THE SAME key (server dedupes; worst case you
   get back the already-created job). Only an intentional new attempt (after `failed`, or
   user edits the draft) generates a fresh key.
2. **Async posting is normal** — never imply instant receipts. The voucher number appears
   only via `done` status. Cron-driven workers mean p95 latency ≈ up to a minute; the
   copy says so.
3. **Branch scoping is invisible but absolute** — reps never choose a branch anywhere.
   Their branch name displays as a passive badge.
4. **Money math stays client-side strings** — compute with integers-of-kobo or a decimal
   lib; format for humans; transmit plain 2dp strings.
5. **Lists have no server pagination** — implement client-side virtualization + filters.
6. **BUSY masters are read-only** — products, categories, branches, sales people screens
   are lookup/reference UIs; the only writable product field is `barcode`.

## 9. Future-proofing (design tokens only, no screens)

Nav placeholders exist for Loyalty, Credit Partners, Payments (Moniepoint), and real Sale
Orders/receipts. Keep the shell's routing lazy-loaded and the DataTable/filters generic
so those modules bolt on without redesign. Receipt printing styles anticipate BUSY
read-back receipts replacing the current voucher-number card.

## 10. Acceptance criteria (Definition of Done)

- [ ] Rep can log in, build a 3-line quotation in <60s standing, submit, and see the
      BUSY voucher number arrive without leaving the tablet.
- [ ] Killing Wi-Fi mid-flow loses no draft and produces no double submission
      (same idempotency key reused on retry of the same attempt).
- [ ] Failed job shows BUSY's raw error text + working Retry-with-fresh-key flow.
- [ ] Superadmin can create a user against an active branch and that user immediately
      logs in on another tablet.
- [ ] Barcode scan (keyboard wedge) assigns to the focused product and survives a
      catalog re-sync.
- [ ] Woo push surfaces per-item outcomes including partial failures.
- [ ] All four job statuses render with correct chips/timeline; polling stops on
      terminal states.
- [ ] Landscape 1280×800 and portrait 800×1280 both fully usable; all targets ≥48px.
