# 02 — Service Codes (the full API)

Every request selects one operation via the `SC` header. `UserName` and `Pwd` are required on
**every** call and are omitted from the table below for brevity.

| SC | Name | Purpose | Key headers | Response body on success |
|----|------|---------|-------------|--------------------------|
| **1** | GetXML from Recordset | Run a SQL query against the open company DB | `Qry` (SQL string) | XML string of the resultant recordset |
| **2** | Add Voucher from XML | Insert a new voucher | `VchType`, `VchXml` | New **Voucher Code** (long) generated |
| **3** | Modify Voucher by Voucher No. | Update a voucher, keyed by voucher number | `VchType`, `VchXml`, `ModifyKey` | `Result` only |
| **4** | Modify Voucher by Voucher Code | Update a voucher, keyed by its unique code | `VchType`, `VchXml`, `VchCode` | Voucher Code (long) |
| **5** | Add Master from XML | Insert a new master (account, item, etc.) | `MasterType`, `MasterXml` | New **Master Code** (long) generated |
| **6** | Modify Master by Code | Update a master, keyed by its code | `MasterCode`, `MasterXml` | Master Code (long) |
| **7** | Modify Master by Name | Update a master, keyed by name | `MasterName`, `MasterType`, `MasterXml` | `Result` only |
| **8** | GetVchXML | Retrieve a voucher's data as XML | `VchCode` | XML string of the voucher |
| **9** | GetMasterXML | Retrieve a master's data as XML | `MasterCode` | XML string of the master |

## `ModifyKey` values (used with SC=3)

The basis on which a voucher is matched for modification:

| Value | Name | Matches on |
|-------|------|-----------|
| 1 | `VCHNO_ONLY` | Voucher No. only |
| 2 | `VCHNO_DATE` | Voucher No. + Date |
| 3 | `VCHNO_SERIES` | Voucher No. + Series |
| 4 | `VCHNO_SERIES_DATE` | Voucher No. + Series + Date |
| 5 | `VCHCODE_ONLY` | Voucher Code |

## Reading the response (from the VB sample)

```
result = response.Header["Result"]      ' "T" or "F"
if result == "T":
    data = response.Body                 ' e.g. the new VchCode / recordset XML
else:
    error = response.Header["Description"]
```
