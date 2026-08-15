# 10 — Proposal: In‑house POS + BUSY + Payment‑machine integration

**Goal:** replace paper order forms and the hand‑written cashier book with one in‑house app,
where **BUSY is the backend system of record**, receipts come **from BUSY**, and card/transfer
payments are taken by **integrating directly with the Moniepoint / Opay terminals** — built for
**reliability with no room for errors**.

---

## 1. The model in one line

> **BUSY becomes the backend (the ledger / "last guy"). Sales reps and cashiers only ever use our
> in‑house app. BUSY records every sale and issues the official invoice number, which the app then
> prints as the receipt.**

Three layers:

```
 In‑house app (reps + cashiers)  →  Connector  →  BUSY  (records sale, issues invoice no.)
 Payment machine (Moniepoint/Opay) ←→ app        (system of record + official receipt data)
```

- **In‑house app** — the only screen staff touch: build orders, take payment, print receipts.
- **Connector** — the pipe to BUSY's web service (port 981), with a queue + idempotency.
- **BUSY** — accounting system of record; assigns the official voucher/invoice number.
- **Payment machine API** — app tells the terminal what to collect and gets automatic confirmation.

## 2. Hosting

| Piece | Where | Why |
|-------|-------|-----|
| Connector | **On the BUSY server** | Talks to BUSY at `localhost:981` — no ports exposed to the internet, no whitelisting headache. |
| In‑house POS app | **On the server** (served to store tablets/PCs over the network) | Internal use; central, easy to update. |
| Public e‑commerce website | **Stays on cPanel** | Unchanged; it calls the connector's API. |

## 3. The shop‑floor flow (rep → cashier → payment → BUSY → receipt)

1. **Sales rep** builds the order on a tablet. App creates a short **order code** (e.g. `#A‑1043`)
   and a matching **QR code**.
2. Order instantly appears in the **cashier's "Pending Orders"** list — nothing printed, nothing
   re‑typed.
3. Customer goes to the till. Cashier **selects the order** by scanning the QR, tapping it, or
   typing `A‑1043`.
4. Cashier taps **Collect Payment** and picks the method:
   - **Cash** → enter amount, drawer updates. (Reconciled by drawer count — see §6.)
   - **Card / Transfer** → app **pushes the exact amount to that cashier's terminal** via the
     Moniepoint/Opay API. Customer taps card or transfers **on the machine**. App receives
     automatic **confirmation** (webhook + polling). The cashier never types the amount.
5. **Only after payment is confirmed**, the app posts the **Sale (VchType 9)** + **Receipt
   (VchType 14)** to BUSY through the connector. BUSY returns the **official invoice number / VchCode**.
6. The app prints the **receipt using BUSY's data and invoice number** → the paper is a genuine
   BUSY receipt.
7. Everything is stored (order, payment reference, BUSY VchCode) for reconciliation.

**Order code = the identifier** linking the rep's order to the cashier's payment. QR scan is
smoothest; typing the code is the fallback.

## 4. "Receipt comes from BUSY" — how

BUSY is the source of the official document:

- The sale is saved to BUSY **first** (synchronously at finalize — a ~1–2 second wait).
- We let **BUSY assign the voucher/invoice number** (auto‑numbering), so the number is official.
- The app prints from **BUSY's saved record** (data pulled via `SC=8` or the values BUSY returns).
- Result: the printed receipt **always matches the ledger exactly** — no drift between paper and BUSY.

> Edge case: if BUSY is briefly unreachable *after* payment is taken, the sale is held in the
> connector's durable queue and the receipt prints the moment BUSY confirms. Because BUSY is
> always‑on, this is rare — but the queue guarantees no lost sale.

## 5. Payment‑machine integration (Moniepoint / Opay)

### Moniepoint POS API (confirmed capabilities)
- **Auth:** Bearer token via `POST /v1/auth` (API key + secret from the Moniepoint dashboard).
- **Push payment to terminal:** `POST /v1/transactions` with:
  - `terminalSerial` — the exact terminal to collect on,
  - `amount`,
  - `merchantReference` — **our order code**, used as an **idempotency key** (resubmitting the same
    reference is rejected → **no double charge**),
  - `transactionType` = `PURCHASE`,
  - `paymentMethod` = `CARD_PURCHASE` | `POS_TRANSFER` | `ANY`.
- **Result:** initial call returns `202 Accepted`; outcome via **polling**
  `GET /v1/transactions/merchants/{merchantReference}` (`processingStatus`, `actualPaymentMethod`,
  `actualAmount`) **and webhook** event `V1_POS_TRANSACTION`.

### Opay POS API
- Card‑present acceptance via Opay POS terminals; **webhook** URL configured in the Business
  Dashboard → Developer Tool → "POS & Others". Auth via **HMAC SHA‑512** signature + `MerchantId`.

### Why this is reliable
- The **amount is pushed by the app** — the cashier cannot mistype it on the machine.
- **Confirmation is automatic** — the sale only proceeds when the provider says "paid."
- `merchantReference` (= order code) makes the charge **idempotent** — retries never double‑charge.
- The machine reports the **actual** amount and method back, so the record is the provider's truth.

## 6. Payment types & reconciliation (auditor sees exceptions, not paper)

| Method | Source of truth | How it reconciles |
|--------|-----------------|-------------------|
| **Cash** | Physical count | App computes **expected** (float + cash sales − payouts); cashier **blind‑counts**; system shows **variance**. Cash **banked** later matches the **bank statement**. |
| **Card / Transfer on machine** | Moniepoint/Opay records | App's confirmed payments **↔ provider dashboard/settlement** (auto‑matched by `merchantReference`). |
| **Direct bank transfer** | Bank statement | App's recorded transfers **↔ bank credits**. |

All three, plus BUSY's receipt vouchers, feed **one reconciliation dashboard** that flags mismatches.
BUSY holds the authoritative account balances (Cash, each bank/wallet).

## 7. Reliability — the "no room for error" checklist

- ☑ **Payment before sale** — no BUSY sale is created until payment is confirmed.
- ☑ **Amount pushed to terminal** — no manual amount entry on the machine.
- ☑ **Idempotency everywhere** — `merchantReference` at the terminal; `orderCode → VchCode` at BUSY.
- ☑ **Receipt from BUSY** — paper always equals the ledger.
- ☑ **Durable queue + retry** — a momentary BUSY hiccup never loses a paid sale.
- ☑ **Blind cash count + per‑cashier drawer** — cash shortages are attributable and can't be fudged.
- ☑ **Automatic three‑way reconciliation** — cash count, provider settlement, BUSY vouchers.

## 8. Suggested rollout

1. **Connector + read‑only extraction** (schema + catalog/stock/price dump).
2. **One pilot branch:** rep→cashier order flow, **Moniepoint** push‑payment integration, BUSY sale
   + receipt, cash‑up report. Prove it removes the paper form and the cashier book.
3. **Reconciliation dashboard** (cash variance + provider settlement + BUSY).
4. **Roll out** to remaining branches; add Opay/other terminals as needed.

## 9. Open items to confirm

- ☐ Which **terminal providers** per branch (Moniepoint, Opay, Squad, PalmPay) → API access + keys.
- ☐ Get **API credentials** and each **terminalSerial** from the provider dashboards.
- ☐ Confirm **BUSY auto‑numbering** is on for the online/POS voucher series (official invoice no.).
- ☐ Receipt **format/branding** to print from BUSY data.
- ☐ Per‑branch **Material Center** + **Voucher Series** names for posting in‑store sales.

## Appendix A — Worked example: tracking a cash sale

**Start of shift.** Cashier **Bola** signs in to **Till 1** and enters the **opening float ₦20,000**.
The app now knows: *Expected cash = ₦20,000.*

**One cash sale, step by step:**
1. Sales rep builds order **`#A-1043`** — 1 Blender, **₦15,000** — it appears in Bola's queue.
2. Bola taps `#A-1043`; customer pays **cash**, hands over ₦20,000.
3. Bola taps **Cash**, enters tendered ₦20,000 → app shows **change ₦5,000**.
4. On confirm, the sale is tracked in **three places at once:**

| Where | What it records |
|-------|-----------------|
| The app | Order `#A-1043`, Cash, ₦15,000, change ₦5,000, cashier Bola, Till 1, time |
| BUSY (via connector) | **Sale** + **Receipt** debiting **Cash ₦15,000**; returns invoice **`CS/0456`** |
| Drawer (expected) | Expected cash **+₦15,000** → ₦35,000 |

5. App prints BUSY receipt `CS/0456`; Bola gives ₦5,000 change.
   (Drawer rises by the **sale amount ₦15,000**, not the ₦20,000 tendered — the app tracks the net.)

**The day builds up:**

| Order | Method | Drawer effect | Expected cash |
|-------|--------|---------------|---------------|
| Opening float | — | — | ₦20,000 |
| `#A-1043` Blender | Cash | +₦15,000 | ₦35,000 |
| `#A-1044` Laptop | Card (Moniepoint) | ₦0 (money to Moniepoint) | ₦35,000 |
| `#A-1045` Kettle | Cash | +₦8,000 | ₦43,000 |
| Fuel (petty cash) | Cash payout | −₦3,000 | ₦40,000 |

- Card sales **don't touch the drawer** — they reconcile against Moniepoint.
- Cash payouts are entered in the app, keeping "expected" accurate (this used to be the paper book).

**Cash-up (honesty check).** Bola **blind-counts** the drawer (without seeing ₦40,000) and enters
**₦39,500** → app shows **variance −₦500 (short)**, attributed to Bola's shift, supervisor signs off,
BUSY gets a small **Journal to "Cash Over/Short."**

**Banking (external anchor).** Bola keeps ₦20,000 float and **banks ₦20,000** → app records a
**Contra (Cash → Bank)**; next day **₦20,000 appears on the bank statement**.

**What the auditor sees** (instead of three books):
- App cash sales ₦23,000 **=** BUSY cash receipts ₦23,000 ✅
- Variance −₦500, signed off ✅
- Banked ₦20,000 **=** bank statement ₦20,000 ✅

A cash sale is tracked at the **point of sale (app)**, in the **ledger (BUSY Cash account)**, and in
the **physical drawer** — tied together by three checks: **expected‑vs‑counted**, **app‑vs‑BUSY**,
and **banking‑vs‑bank‑statement.**

## References

- Moniepoint POS API documentation — https://docs.pos.moniepoint.com/
- Moniepoint "Push Payment Request" API reference — https://teamapt.atlassian.net/wiki/spaces/EI/pages/1039826999/Push+Payment+Request+API+Reference
- Opay POS Integration (API) — https://documentation.opayweb.com/doc/offline/pos-api.html
- Opay developer documentation — https://doc.opaycheckout.com/
