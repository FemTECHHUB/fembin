# 12 — Real BUSY schema findings (from the live probe)

Captured from the first successful `npm run probe` run against the real server
(`45.248.123.58:981`, company logged in as user `Joshua`). Backend confirmed to be
**SQL Server** (responses use Microsoft's ADO XML-persistence rowset format).

---

## 1. Confirmed real tables (from `INFORMATION_SCHEMA.TABLES`)

Core tables: `Master1`, `Tran1`, `Tran2`...`Tran12` (12 transaction detail tables — more
than the 2 we assumed), `MasterAddressInfo`, `MasterSupport`, `MastFootPrint`.

**E-commerce / POS tables already present in this BUSY install:**
- `EComOrderHeader`, `EComOrderBody`
- `EcomSettlement`, `EcomSettlementExp`, `EcomSettlementItem`, `EcomSettlementItemExp`
- `POSDet`
- `VchDataMobileApp`

**Sync / change-tracking tables (worth investigating — may overlap our cache-sync plan):**
- `CloudSyncIncr`, `CloudSyncIncrDet`, `CloudSyncStatus`, `DataSync`

**Audit / logging:**
- `EventLog`, `QueryLog`, `CSAuditLog`, `CSAuditLogDet`, `DeletedInfo`, `DeletedMasters`

**Other notable:** `ItemDesc`, `ItemParamDet`, `ItemSerialNo`, `GSTInfo`, `EPaymentDet`,
`BillingDet`, `Images`, `Help1`/`Help2` (field-name legends — see §5).

> ⚠️ **Action:** check the BUSY GUI (Administration menu) for a licensed **"E-Commerce" /
> "POS" module**. The `EComOrderHeader/Body`, `EcomSettlement*`, `POSDet` tables and the
> `EcomOrderID`/`EcomOrderItemID` columns (see below) strongly suggest BUSY has a native
> integration path — worth knowing before building a custom one.

---

## 2. `Master1` — every master type, one wide table

Key columns:

| Column | Type | Notes |
|---|---|---|
| `Code` | int | Primary key / MasterCode |
| `MasterType` | smallint | Matches our [MasterType constants](03-constants.md) |
| `Name`, `Alias`, `PrintName` | nvarchar | |
| `ParentGrp` | int | Parent group reference |
| `Stamp` | int | **Likely change-tracking value — candidate for incremental sync** |
| `CreatedBy` / `CreationTime` | nvarchar / datetime | Full audit trail |
| `ModifiedBy` / `ModificationTime` | | |
| `AuthorisedBy` / `AuthorisationTime` | | |
| `BlockedMaster`, `DeactiveMaster` | bit | Exclude these from the catalog sync |
| `HSNCode` | nvarchar | Tax classification (for items) |
| `D1`...`D26` | float | **Generic — meaning depends on MasterType** (price, MRP, etc. live here) |
| `I1`...`I30` | smallint | Generic integers |
| `B1`...`B40` | bit | Generic flags |
| `C1`...`C7` | nvarchar | Generic text |
| `CM1`...`CM11` | int | Generic references |

**The catch:** which `D#`/`C#`/`I#` column means "Sale Price," "Unit," etc. is **not**
in the schema — it depends on `MasterType`. Must be reverse-engineered against known data
(see §4).

---

## 3. `Tran1` (voucher header) / `Tran2` (voucher line)

`Tran1` highlights:

| Column | Notes |
|---|---|
| `VchCode`, `VchType`, `VchNo`, `VchSeriesCode`, `AutoVchNo` | Identity |
| `MasterCode1`, `MasterCode2` | The party / material center (matches `MasterName1`/`2` in the XML API) |
| `Stamp` | Same change-tracking candidate as `Master1` |
| `POSEnabled` | bit — a POS flag exists on every voucher |
| `VchCancelled`, `Cancelled` | |
| `ApprovalStatus` | Existing approval-workflow field — may map to our cashier-approve step |
| `EcomOrderID` | ⭐ **nvarchar — built-in slot for our website's order ID** |
| Full audit trail | `CreatedBy/CreationTime/ModifiedBy/.../AuthorisedBy/AuthorisationTime` |
| E-invoice fields | `EInvIRN`, `EInvAckNo`, etc. (India e-invoicing — probably N/A for us) |

`Tran2` highlights (line-level, item or account entries — differentiated by `RecType`):

| Column | Notes |
|---|---|
| `VchCode`, `MasterCode1`, `MasterCode2`, `SrNo` | Identity / links |
| `Value1`, `Value2`, `Value3` | Likely Qty / Price / Amount — confirm against real data |
| `Balance1-3`, `ItemBal1-3` | Running balances — **candidate for stock levels** |
| `TrackingStatus`, `TrackingNo` | Shipment tracking fields already exist |
| `EcomOrderItemID` | ⭐ **nvarchar — built-in slot for our website's order line-item ID** |
| `D1`...`D39`, `I1`...`I10`, `C1`...`C4` | Generic — meaning depends on `VchType`/`RecType` |

---

## 4. Next step: crack the generic-column mapping

1. Pick **one known item** in the BUSY GUI — note its exact Code, Name, Sale Price, MRP, Stock.
2. Query `SELECT * FROM Master1 WHERE Code = <that code>` via the probe.
3. Match the real values to the `D#`/`C#`/`I#` columns → build the field map for `MasterType=6` (Item).
4. Repeat for one known **Sale** voucher: query `Tran1 WHERE VchCode = <code>` and its
   `Tran2` rows, matching `Value1-3`/`D#` to Qty/Price/Amount/Tax.
5. Do the same for `MasterType=2` (Account) if account-specific fields are needed.

This mapping only has to be done once per MasterType/VchType we actually use — not for all 34.

---

## 5. Possible shortcut: `Help1`/`Help2` tables

These table names (`Help1`, `Help1AddnInfo`, `Help2`) look like they might hold **field-name
legends or metadata** BUSY uses internally. Worth a quick `SELECT *` on `Help1` — if it
documents what `D1`..`D26` mean per MasterType, it could save all the manual correlation in §4.

---

## 6. Connection recap (for the record)

- Real issue was **Windows Firewall** blocking 981 (not an edge firewall as first suspected).
- Fixed with: `netsh advfirewall firewall add rule name="BUSY Web Service 981" dir=in action=allow protocol=TCP localport=981`.
- BUSY backend: `Server: WeOnlyDo! wodWebServer, version 1.6.4.346`.
- ⚠️ Security follow-up still open: the 981 rule currently allows **any source IP**, and
  traffic is plaintext HTTP. Restrict to the connector's IP (and consider TLS) before go-live.
