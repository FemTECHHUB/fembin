"""BUSY serialises bit columns as text — `'True'`/`'False'`, not `'1'`/`'0'` (a real bug
found against live data during the research phase; see CLAUDE.md §8). Check both forms
defensively rather than trusting either encoding alone.
"""

_TRUTHY = {"true", "1"}


def is_bit_true(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUTHY


def is_master_active(row: dict[str, str]) -> bool:
    """A master is active unless BUSY marked it Blocked or Deactivated."""
    return not is_bit_true(row.get("BlockedMaster")) and not is_bit_true(row.get("DeactiveMaster"))
