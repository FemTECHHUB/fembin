# Real XML fixtures — provenance

Per CLAUDE.md §5: real captured data, not invented shapes. Two kinds of fixture here:

**Raw captures, byte-for-byte from the Node prototype's `output/` folder**
(`../../../../Busin/code/busy-probe/output/2026-08-14T14-15-35-519Z/`):
- `tables_rowset.xml` — `INFORMATION_SCHEMA.TABLES` (SC=1)
- `columns_master1_rowset.xml`, `columns_tran1_rowset.xml`, `columns_tran2_rowset.xml` —
  `INFORMATION_SCHEMA.COLUMNS` per table (SC=1)
- `vchno_sample_rowset.xml` — real `VchNo` values from `Tran1`, **truncated to the first 300 of
  9,705 real rows** to keep the fixture small; the padding (`VchNo='                        1'`)
  is genuine — this is the real data behind the "VchNo is padded" gotcha in CLAUDE.md §8.

**Reconstructed from real field values, not raw captures** (the original raw XML wasn't saved to
disk during the research phase — only the parsed values were):
- `item_master_xml.xml` — re-serialized from `catalog-2026-08-14T13-32-13-338Z/items.json`
  (Item code 1613, "Cable-infinix Micro"), which itself came from a real `GetMasterXML` call.
  Field names, nesting, and values are all real; only the XML text encoding was regenerated.
- `customers_with_entities_rowset.xml` — reproduces the two real bugs documented in
  `docs/reference/14-command-center.md` §"Two real bugs found": a customer name that came back
  as `&#x27;ENAIBE L C (MRS)` (numeric entity, not one of the 5 named entities) and a blocked
  master with `BlockedMaster='True'` (text, not `'1'`). The original raw response wasn't
  archived; these values are transcribed verbatim from the incident write-up.
