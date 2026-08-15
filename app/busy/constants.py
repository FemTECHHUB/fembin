"""BUSY constants: service codes, master types, voucher types.

Source of truth: docs/reference/02-service-codes.md, docs/reference/03-constants.md
(derived from *Master and Voucher types.pdf*). Never use a bare int for one of these
in application code — always the enum.
"""

from enum import IntEnum


class ServiceCode(IntEnum):
    """The `SC` header value selecting which BUSY web-service operation to run."""

    GET_XML_FROM_RECORDSET = 1
    """Run a SQL query against the open company DB (`Qry` header) -> recordset XML."""
    ADD_VOUCHER = 2
    """Insert a new voucher (`VchType`, `VchXml`) -> new Voucher Code."""
    MODIFY_VOUCHER_BY_NO = 3
    """Update a voucher keyed by voucher number (`VchType`, `VchXml`, `ModifyKey`)."""
    MODIFY_VOUCHER_BY_CODE = 4
    """Update a voucher keyed by its unique code (`VchType`, `VchXml`, `VchCode`)."""
    ADD_MASTER = 5
    """Insert a new master (`MasterType`, `MasterXml`) -> new Master Code."""
    MODIFY_MASTER_BY_CODE = 6
    """Update a master keyed by its code (`MasterCode`, `MasterXml`)."""
    MODIFY_MASTER_BY_NAME = 7
    """Update a master keyed by name (`MasterName`, `MasterType`, `MasterXml`)."""
    GET_VOUCHER_XML = 8
    """Retrieve a voucher's full data as XML (`VchCode`)."""
    GET_MASTER_XML = 9
    """Retrieve a master's full data as XML (`MasterCode`)."""


class ModifyKey(IntEnum):
    """Basis on which a voucher is matched for modification (used with SC=3)."""

    VCHNO_ONLY = 1
    VCHNO_DATE = 2
    VCHNO_SERIES = 3
    VCHNO_SERIES_DATE = 4
    VCHCODE_ONLY = 5


class MasterType(IntEnum):
    """The `MasterType` header — which kind of master record is being addressed."""

    ACCOUNT_GROUP = 1
    ACCOUNT = 2
    """Ledger accounts — customers, suppliers, banks, cash, expense/income heads."""
    COST_CENTER_GROUP = 3
    COST_CENTER = 4
    ITEM_GROUP = 5
    """Product category tree."""
    ITEM = 6
    """Products / SKUs — name, unit, price, tax category, stock."""
    CURRENCY = 7
    UNIT = 8
    """Units of measure (Pcs., Kg.m, Dozen)."""
    BILL_SUNDRY = 9
    """Charge/discount lines (Discount, Freight, Round-off)."""
    MATERIAL_CENTER_GROUP = 10
    MATERIAL_CENTER = 11
    """Stores / warehouses / godowns (stock locations)."""
    FORM = 12
    SALE_TYPE = 13
    """Sale tax/transaction templates (e.g. Local-ItemWise)."""
    PURCHASE_TYPE = 14
    BILL_OF_MATERIAL = 15
    UNIT_CONVERSION = 16
    CURRENCY_CONVERSION = 17
    STANDARD_NARRATION = 18
    BROKER = 19
    AUTHOR = 20
    VOUCHER_SERIES = 21
    """Numbering series per voucher type (e.g. Main)."""
    TDS = 22
    BRANCH = 24
    TAX_CATEGORY = 25
    """GST/tax categories (e.g. GST 18%)."""
    MASTER_SERIES_GROUP = 26
    EMPLOYEE = 27
    EMPLOYEE_GROUP = 28
    SALARY_COMPONENT = 29
    DISCOUNT_STRUCTURE = 30
    MARKUP_STRUCTURE = 31
    SCHEME = 32
    EXECUTIVE = 33
    """Sales executives / salesmen."""
    CONTACT_GROUP = 34
    CONTACT = 36
    # Note: values 23 and 35 are not defined by BUSY.


class VchType(IntEnum):
    """The `VchType` header — which kind of voucher is being addressed."""

    PURCHASE = 2
    SALE_RETURN = 3
    MATERIAL_RECEIPT = 4
    STOCK_TRANSFER = 5
    PRODUCTION = 6
    UNASSEMBLE = 7
    STOCK_JOURNAL = 8
    SALE = 9
    """Sale / invoice to a customer."""
    PURCHASE_RETURN = 10
    MATERIAL_ISSUE = 11
    SALE_ORDER = 12
    PURCHASE_ORDER = 13
    RECEIPT = 14
    """Money received from a customer."""
    CONTRA = 15
    JOURNAL = 16
    """General accounting adjustment."""
    DEBIT_NOTE = 17
    CREDIT_NOTE = 18
    PAYMENT = 19
    """Money paid out."""
    FORMS_RECEIVED = 21
    FORMS_ISSUED = 22
    SALE_QUOTATION = 26
    PURCHASE_QUOTATION = 27
    SALARY_CALCULATION = 28
    CALL_RECEIPT = 29
    CALL_ALLOCATION = 30
    PURCHASE_INDENT = 31
    CALL_REPORT = 32
    PHYSICAL_STOCK = 61
    # Note: values not listed above (1, 20, 23-25, 33-60, ...) are not defined by BUSY.
