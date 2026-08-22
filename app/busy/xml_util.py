"""Parsers for the two XML shapes BUSY returns.

Ported from ``../Busin/code/busy-probe/src/xmlUtil.js`` — same two shapes, same
entity-decoding fix. Kept dependency-free (regex-based, no lxml/ElementTree) to
stay a faithful line-for-line port of the validated prototype rather than a
reimplementation from memory.

  1. ``parse_rowset_xml`` — the ADO "persist XML" rowset format from SC=1 SQL
     queries (``<xml>...<rs:data><z:row A='1' B='2'/>...</rs:data></xml>``) ->
     list of plain row dicts.
  2. ``parse_element_xml`` — the simple nested-tag format from SC=8/SC=9
     (GetVchXML/GetMasterXML), e.g. ``<Account><Name>X</Name>...</Account>`` ->
     a plain nested dict. Repeated sibling tags fold into a list.
"""

import re
from dataclasses import dataclass, field
from typing import TypeAlias

# Plain-assignment alias, not a PEP 695 `type` statement: the deployment host's
# newest interpreter is 3.11 (cPanel Setup Python App), and `type X = ...` is
# 3.12+-only syntax that fails at import time there.
XmlValue: TypeAlias = str | dict[str, "XmlValue | list[XmlValue]"]

_NAMED_ENTITIES = (
    ("&lt;", "<"),
    ("&gt;", ">"),
    ("&quot;", '"'),
    ("&apos;", "'"),
)
_HEX_ENTITY_RE = re.compile(r"&#x([0-9a-fA-F]+);")
_DEC_ENTITY_RE = re.compile(r"&#(\d+);")

_ROWSET_DATA_RE = re.compile(r"<rs:data>(.*?)</rs:data>", re.DOTALL)
_ROW_RE = re.compile(r"<z:row\b(.*?)/>", re.DOTALL)
_ATTR_RE = re.compile(r"""([\w:.\-]+)=(['"])(.*?)\2""", re.DOTALL)

_TAG_RE = re.compile(r"<([\w:.\-]+)(?:\s+[\w:.\-]+=(?:'[^']*'|\"[^\"]*\"))*\s*(/)?>|</([\w:.\-]+)>")


def decode_xml_entities(s: str) -> str:
    """Decode XML entities BUSY emits, including numeric refs (`&#x27;`) real
    customer-name data contains — not covered by decoding only the 5 named
    entities (a real bug found against live data in the Node prototype)."""
    for entity, char in _NAMED_ENTITIES:
        s = s.replace(entity, char)
    s = _HEX_ENTITY_RE.sub(lambda m: chr(int(m.group(1), 16)), s)
    s = _DEC_ENTITY_RE.sub(lambda m: chr(int(m.group(1))), s)
    # &amp; must be decoded last — doing it earlier could re-trigger the rules above.
    return s.replace("&amp;", "&")


def encode_xml_entities(s: str) -> str:
    """Escape the characters that must not appear literally when building outgoing XML."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_rowset_xml(xml: str) -> list[dict[str, str]]:
    """Parse an SC=1 ADO rowset (`<rs:data><z:row .../></rs:data>`) into row dicts."""
    data_match = _ROWSET_DATA_RE.search(xml)
    if not data_match:
        return []
    rows: list[dict[str, str]] = []
    for row_match in _ROW_RE.finditer(data_match.group(1)):
        row: dict[str, str] = {}
        for attr_match in _ATTR_RE.finditer(row_match.group(1)):
            row[attr_match.group(1)] = decode_xml_entities(attr_match.group(3))
        rows.append(row)
    return rows


@dataclass
class _Node:
    name: str
    children: list["_Node"] = field(default_factory=list)
    text: str = ""


def parse_element_xml(xml: str) -> XmlValue:
    """Parse the SC=8/SC=9 nested-element XML shape into a plain nested dict.

    Repeated sibling tags with the same name fold into a list, matching the
    shape callers already rely on (e.g. multiple `<Item>` rows under a voucher).
    """
    root = _Node(name="#root")
    stack: list[_Node] = [root]
    last_index = 0

    for match in _TAG_RE.finditer(xml):
        text_before = xml[last_index : match.start()]
        last_index = match.end()
        top = stack[-1]
        if text_before:
            top.text += text_before

        closing_tag = match.group(3)
        if closing_tag is not None:
            if len(stack) > 1:
                stack.pop()
            continue

        tag_name = match.group(1)
        self_close = match.group(2)
        node = _Node(name=tag_name)
        top.children.append(node)
        if not self_close:
            stack.append(node)

    return _fold(root)


def _fold(node: _Node) -> XmlValue:
    if not node.children:
        return decode_xml_entities(node.text.strip())

    obj: dict[str, XmlValue | list[XmlValue]] = {}
    for child in node.children:
        value = _fold(child)
        existing = obj.get(child.name)
        if existing is None:
            obj[child.name] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            obj[child.name] = [existing, value]
    return obj
