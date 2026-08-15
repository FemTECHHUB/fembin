# 03 — Constants: Master Types & Voucher Types (full reference)

Complete integer constants for the `MasterType` and `VchType` headers, with a short note on what
each represents and whether it matters for the e‑commerce/POS integration.
Source: *Master and Voucher types.pdf*.

Legend: **★** = high priority for our integration.

## Master Types (`MasterType`)

| Value | Master | What it is / holds | Pri |
|------:|--------|--------------------|:---:|
| 1 | Account Group | Tree groups for ledger accounts (e.g. Sundry Debtors, Sundry Creditors) | |
| 2 | **Account** | Ledger accounts — customers, suppliers, banks, cash, expense/income heads | ★ |
| 3 | Cost Center Group | Groupings for cost centers | |
| 4 | Cost Center | Cost-tracking dimensions (projects, departments) | |
| 5 | **Item Group** | Product category tree | ★ |
| 6 | **Item** | Products / SKUs — name, unit, price, tax category, stock | ★ |
| 7 | Currency | Currencies used | |
| 8 | **Unit** | Units of measure (Pcs., Kg.m, Dozen) | ★ |
| 9 | **Bill Sundry** | Charge/discount lines (Discount, Freight, Round-off) | ★ |
| 10 | Material Center Group | Groupings for stores/warehouses | |
| 11 | **Material Center** | Stores / warehouses / godowns (stock locations) | ★ |
| 12 | Form | Statutory forms | |
| 13 | **Sale Type** | Sale tax/transaction templates (e.g. Local-ItemWise) | ★ |
| 14 | Purchase Type | Purchase tax/transaction templates | |
| 15 | Bill of Material | Production BOM definitions | |
| 16 | Unit Conversion | Main↔alternate unit conversion factors | |
| 17 | Currency Conversion | Exchange rates | |
| 18 | Standard Narration | Reusable narration text | |
| 19 | Broker | Brokers / agents | |
| 20 | Author | Authors (book-trade installs) | |
| 21 | **Voucher Series** | Numbering series per voucher type (e.g. Main) | ★ |
| 22 | TDS | TDS rate masters | |
| 24 | Branch | Branches | |
| 25 | **Tax Category** | GST/tax categories (e.g. GST 18%) | ★ |
| 26 | Master Series Group | Series groupings | |
| 27 | Employee | Payroll employees | |
| 28 | Employee Group | Payroll employee groups | |
| 29 | Salary Component | Payroll salary components | |
| 30 | Discount Structure | Named discount rules | |
| 31 | Markup Structure | Named markup/pricing rules | |
| 32 | Scheme | Schemes / offers | |
| 33 | Executive | Sales executives / salesmen | |
| 34 | Contact Group | CRM contact groups | |
| 36 | Contact | CRM contacts | |

> Note: values 23 and 35 are not defined in the source list.

## Voucher Types (`VchType`)

| Value | Voucher | What it records | Pri |
|------:|---------|-----------------|:---:|
| 2 | Purchase | Goods bought | |
| 3 | Sale Return | Goods returned by customer | |
| 4 | Material Receipt | Stock received (non-purchase) | |
| 5 | Stock Transfer | Stock moved between centers | |
| 6 | Production | Manufactured output | |
| 7 | Unassemble | Reverse of production | |
| 8 | Stock Journal | Stock adjustment | |
| 9 | **Sale** | Sale / invoice to a customer | ★ |
| 10 | Purchase Return | Goods returned to supplier | |
| 11 | Material Issue | Stock issued (non-sale) | |
| 12 | Sale Order | Customer order (stock reservation) | |
| 13 | Purchase Order | Order placed on a supplier | |
| 14 | **Receipt** | Money received from a customer | ★ |
| 15 | Contra | Cash↔bank / bank↔bank transfer | |
| 16 | **Journal** | General accounting adjustment | ★ |
| 17 | Debit Note | Debit adjustment to a party | |
| 18 | Credit Note | Credit adjustment to a party | |
| 19 | **Payment** | Money paid out | ★ |
| 21 | Forms Received | Statutory forms received | |
| 22 | Forms Issued | Statutory forms issued | |
| 26 | Sale Quotation | Quote to a customer | |
| 27 | Purchase Quotation | Quote requested from supplier | |
| 28 | Salary Calculation | Payroll run | |
| 29 | Call Receipt | Service call logged | |
| 30 | Call Allocation | Service call assigned | |
| 31 | Purchase Indent | Internal purchase request | |
| 32 | Call Report | Service call report | |
| 61 | Physical Stock | Physical stock count entry | |

> Note: values not listed (1, 20, 23–25, 33–60, …) are not defined in the source.

## How these constants are used

- **`MasterType`** → header for `SC=5` (add master), `SC=7` (modify master by name).
- **`VchType`** → header for `SC=2` (add voucher), `SC=3`/`SC=4` (modify voucher).
- For pulling data in bulk, see [07-data-extraction.md](07-data-extraction.md).
