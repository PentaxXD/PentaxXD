import re
from dataclasses import dataclass, asdict
from typing import Iterable, List, Optional, Tuple, Dict, Any


IGNORED_HEADER_PATTERNS = [
    r"^Gourmet\s+International$",
    r"^5253\s+Patterson\s+Ave\s+SE$",
    r"^Grand\s+Rapids\s+MI\s+49512$",
    r"^United\s+States$",
    r"^Phone\s*#:\s*\(.+\)$",
    r"^sales@gourmetint\.com$",
    r"^Invoice$",
    r"^#?INV\d+$",
    r"^Sales\s+Order\s+#?SO\d+$",
    r"^\d+\s+of\s+\d+$",
    r"^Bill\s+To\s+Ship\s+To$",
    r"^BAVARIA\s+SAUSAGE\s+INC$",
    r"^6317\s+NESBITT\s+RD$",
    r"^ATTN:\s+LISA$",
    r"^MADISON\s+WI\s+53719$",
    r"^PO\s+#\s+Created\s+By\s+Ship\s+Method\s+Terms\s+Sales\s+Rep\s+Due\s+Date\s+Date$",
    r"^HOL\s+\S+\s+LS\s+\S+\s+LTL\s+NET30\s+\S+$",
    r"^\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}/\d{1,2}/\d{4}$",
]

COLUMN_HEADER_PATTERN = re.compile(
    r"^Order\s+Qty\s+Ship\s+Qty\s+Units\s+Item\s+UPC\s+Brand\s+Description\s+Pack\s+Size\s+Price\s+Ext\.\s*Price$",
    re.IGNORECASE,
)

ORDER_LINE_START = re.compile(
    r"^(?P<order>\d+)\s+(?P<ship>\d+)\s+(?P<units>[A-Z]{2}\d{3})\s+(?P<item>\d{5,})$"
)
UPC_LINE = re.compile(r"^(?P<upc>\d{12,13})$")
PRICE_LINE = re.compile(
    r"^(?P<pack>\d+\/[\d.]+\s*OZ|\d+\/[\d.]+\s*LB|\d+\/[\d.]+\s*G|\d+\/[\d.]+\s*KG)\s+\$(?P<price>[0-9,.]+)\s+\$(?P<ext>[0-9,\.]+)$",
    re.IGNORECASE,
)


@dataclass
class LineItem:
    order_qty: int
    ship_qty: int
    units: str
    item: str
    upc: str
    brand: str
    description: str
    pack_size: str
    price: float
    extended_price: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _is_ignored(line: str) -> bool:
    s = line.strip()
    for pattern in IGNORED_HEADER_PATTERNS:
        if re.match(pattern, s, flags=re.IGNORECASE):
            return True
    return False


def parse_line_items(text: str) -> List[LineItem]:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]

    # skip everything until column header appears
    idx = 0
    while idx < len(lines) and not COLUMN_HEADER_PATTERN.match(lines[idx]):
        idx += 1
    if idx == len(lines):
        # column header not found; try a more permissive approach: look for first ORDER_LINE_START
        idx = 0
    else:
        idx += 1  # move past header

    items: List[LineItem] = []

    while idx < len(lines):
        line = lines[idx].strip()
        if _is_ignored(line):
            idx += 1
            continue

        start_match = ORDER_LINE_START.match(line)
        if not start_match:
            idx += 1
            continue

        order_qty = int(start_match.group("order"))
        ship_qty = int(start_match.group("ship"))
        units = start_match.group("units")
        item = start_match.group("item")
        idx += 1

        if idx >= len(lines):
            break
        m_upc = UPC_LINE.match(lines[idx].strip())
        if not m_upc:
            # UPC expected; if missing, skip this block
            continue
        upc = m_upc.group("upc")
        idx += 1

        # Brand may occupy one or more lines but examples show two lines for ABTEY CHOCOLATIERIE.
        # We'll collect up to two brand lines if both are ALLCAPS alphabetic words, then description lines until price line.
        brand_parts: List[str] = []
        while idx < len(lines):
            token = lines[idx].strip()
            if PRICE_LINE.match(token):
                break
            if UPC_LINE.match(token):
                # shouldn't encounter another UPC before finishing this item; treat as description continuation break
                break
            # Heuristic: brand lines are mostly ALLCAPS words (letters and spaces). Stop when line contains digits.
            if re.match(r"^[A-Z][A-Z\s&.'-]+$", token) and not re.search(r"\d", token):
                brand_parts.append(token)
                idx += 1
            else:
                break

        brand = " ".join(brand_parts).strip()

        description_parts: List[str] = []
        while idx < len(lines):
            token = lines[idx].strip()
            m_price = PRICE_LINE.match(token)
            if m_price:
                pack_size = m_price.group("pack")
                price = float(m_price.group("price").replace(",", ""))
                ext_price = float(m_price.group("ext").replace(",", ""))
                idx += 1
                # finalize record
                items.append(
                    LineItem(
                        order_qty=order_qty,
                        ship_qty=ship_qty,
                        units=units,
                        item=item,
                        upc=upc,
                        brand=brand,
                        description=" ".join(description_parts).strip(),
                        pack_size=pack_size,
                        price=price,
                        extended_price=ext_price,
                    )
                )
                break
            else:
                description_parts.append(token)
                idx += 1

        # If no price line found, attempt to move on
        while idx < len(lines) and not ORDER_LINE_START.match(lines[idx].strip()):
            idx += 1

    return items
