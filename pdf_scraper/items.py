import re
from dataclasses import dataclass, asdict
from typing import Iterable, List, Optional, Tuple, Dict, Any

try:
    import pdfplumber  # type: ignore
except Exception:
    pdfplumber = None  # optional; we can still parse from text


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


def parse_line_items_layout_aware(pdf_path: str, page: int = 1) -> List[LineItem]:
    """Parse items using positional columns; falls back to text parser if pdfplumber missing.

    Uses x-coordinates observed on the sample to bucket tokens into columns.
    """
    if pdfplumber is None:
        # fallback: use text-only path
        from .extractor import extract_text_from_pdf

        text = extract_text_from_pdf(pdf_path, pages=[page])
        return parse_line_items(text)

    items: List[LineItem] = []
    with pdfplumber.open(pdf_path) as pdf:
        p = pdf.pages[page - 1]
        words = p.extract_words(x_tolerance=2, y_tolerance=3, use_text_flow=True)

        # Column x ranges inferred from inspection
        # Left numeric columns: order_qty (~x0 29-36), ship_qty (~59-67), units (~78-97), item (~119-141)
        # UPC appears around x0 ~206-249
        # Brand/description around x0 >= ~300
        # Pack size around x0 ~472-505
        # Price around x0 ~529-553; Ext Price ~569-594
        def bucket_x(x: float) -> str:
            # Column thresholds tuned to observed header x positions
            if x < 50:
                return "order"
            if x < 75:
                return "ship"
            if x < 110:
                return "units"
            if x < 200:
                return "item"
            if x < 270:
                return "upc"
            if x < 360:
                return "brand"
            if x < 470:
                return "desc"
            if x < 520:
                return "pack"
            if x < 565:
                return "price"
            return "ext"

        # Group words by line (y center) with small tolerance
        # Group words by line (y center) with small tolerance; allow small y drift within a row
        rows: List[Dict[str, List[str]]] = []
        row_ys: List[float] = []
        for w in words:
            y_center = (w["top"] + w["bottom"]) / 2.0
            # find existing row within tolerance
            row_idx: Optional[int] = None
            for i, ry in enumerate(row_ys):
                if abs(y_center - ry) <= 3.5:
                    row_idx = i
                    # update tracked row y as running average to keep groups tight
                    row_ys[i] = (ry + y_center) / 2.0
                    break
            if row_idx is None:
                row_idx = len(rows)
                rows.append({"order": [], "ship": [], "units": [], "item": [], "upc": [], "brand": [], "desc": [], "pack": [], "price": [], "ext": []})
                row_ys.append(y_center)
            bucket = bucket_x(w["x0"])
            rows[row_idx][bucket].append(w["text"])

        # Collapse rows into logical items by detecting when price+ext present
        current: Dict[str, Any] = {k: None for k in ["order","ship","units","item","upc","brand","description","pack","price","ext"]}
        brand_buffer: List[str] = []
        desc_buffer: List[str] = []

        number_re = re.compile(r"^[0-9][0-9,]*\.?[0-9]*$")
        units_re = re.compile(r"^[A-Z]{2}\d{3}$")
        item_re = re.compile(r"^\d{5,}$")
        upc_re = re.compile(r"^\d{12,14}$")
        pack_re = re.compile(r"^\d+\/\d+(?:\.\d+)?\s*(?:OZ|LB|G|KG)$", re.IGNORECASE)
        pack_price_re = re.compile(
            r"(?P<pack>\d+\/\d+(?:\.\d+)?\s*(?:OZ|LB|G|KG))\s+\$?(?P<price>[0-9][0-9,]*\.?[0-9]*)\s+\$?(?P<ext>[0-9][0-9,]*\.?[0-9]*)",
            re.IGNORECASE,
        )

        def try_flush():
            if (
                current["order"] and str(current["order"]).isdigit() and
                current["ship"] and str(current["ship"]).isdigit() and
                current["units"] and units_re.match(str(current["units"])) and
                current["item"] and item_re.match(str(current["item"])) and
                current["upc"] and upc_re.match(str(current["upc"])) and
                current["pack"] and pack_re.match(str(current["pack"])) and
                current["price"] and number_re.match(str(current["price"])) and
                current["ext"] and number_re.match(str(current["ext"]))
            ):
                items.append(
                    LineItem(
                        order_qty=int(current["order"]),
                        ship_qty=int(current["ship"]),
                        units=str(current["units"]),
                        item=str(current["item"]),
                        upc=str(current["upc"]),
                        brand=str(current.get("brand") or "").strip(),
                        description=str(current.get("description") or "").strip(),
                        pack_size=str(current["pack"]),
                        price=float(str(current["price"]).replace(",","")),
                        extended_price=float(str(current["ext"]).replace(",","")),
                    )
                )
                for k in list(current.keys()):
                    current[k] = None
                brand_buffer.clear()
                desc_buffer.clear()

        in_items = False

        for r in rows:
            def first_text(key: str) -> Optional[str]:
                vals = r.get(key) or []
                return " ".join(vals) if vals else None

            # Wait until header row detected to start capturing
            if not in_items:
                header_tokens = set(t.lower() for key in ("order","item","desc","pack","price","ext") for t in (r.get(key) or []))
                # More robust header detection based on column names observed
                if {"order","ship","units"}.issubset(header_tokens) and {"item","upc"}.intersection(header_tokens):
                    in_items = True
                elif {"description","price"}.issubset(header_tokens) and ("pack" in header_tokens or "size" in header_tokens):
                    in_items = True
                # Alternatively, if row looks like a first data row
                elif (r["order"] and r["ship"] and r["units"] and (r["item"] or r["upc"])):
                    in_items = True
                else:
                    continue

            # Detect start of a new item row; allow item number to be on the next line
            if r["order"] and r["ship"] and r["units"]:
                # If we already had a partially-filled item, try flushing before starting a new one
                if any(current.get(k) for k in ("order", "ship", "units", "item", "upc", "pack", "price", "ext")):
                    try_flush()
                    # Reset state for a new item
                    brand_buffer.clear()
                    desc_buffer.clear()
                    for k in list(current.keys()):
                        current[k] = None
                else:
                    # Also reset buffers if we're starting for the first time within the items section
                    brand_buffer.clear()
                    desc_buffer.clear()
                    for k in list(current.keys()):
                        current[k] = None

                current["order"] = r["order"][0]
                current["ship"] = r["ship"][0]
                current["units"] = r["units"][0]
                if r["item"]:
                    current["item"] = r["item"][0]

            # If we are in the middle of an item and encounter a row that only has the item number, capture it
            if (not current.get("item")) and r["item"] and not (r["order"] or r["ship"] or r["units"]):
                current["item"] = r["item"][0]

            if not current["upc"]:
                # Most rows have single UPC row after item row
                if r["upc"]:
                    upc_text = "".join(r["upc"]).strip()
                    if re.fullmatch(r"\d{12,14}", upc_text):
                        current["upc"] = upc_text
                else:
                    # Fallback: search for a UPC-like token anywhere in the row
                    combined = " ".join(sum([r.get("upc", []), r.get("desc", []), r.get("brand", [])], []))
                    m_upc_any = re.search(r"\b(\d{12,14})\b", combined)
                    if m_upc_any:
                        current["upc"] = m_upc_any.group(1)

            # brand column handling
            if r.get("brand"):
                brand_text = " ".join(r["brand"]).strip()
                if re.fullmatch(r"[A-Z][A-Z\s&.'-]+", brand_text) and not re.search(r"\d", brand_text):
                    brand_buffer.append(brand_text)
                    current["brand"] = " ".join(brand_buffer)

            # description column handling
            if r["desc"]:
                desc_text = " ".join(r["desc"]).strip()
                if desc_text.lower() not in {"brand", "description", "pack size", "price", "ext. price"}:
                    desc_buffer.append(desc_text)
                    current["description"] = " ".join(desc_buffer)
                    # Opportunistic pack detection within description (handles cases like "... 12/5.99OZ" or "... 12/5.99 OZ")
                    if not current.get("pack"):
                        m_desc_pack = re.search(r"(\d+\/\d+(?:\.\d+)?)\s*(OZ|LB|G|KG)\b", desc_text, flags=re.IGNORECASE)
                        if m_desc_pack:
                            current["pack"] = f"{m_desc_pack.group(1)} {m_desc_pack.group(2).upper()}"

            # pack/price/ext
            if r["pack"]:
                pack_text = " ".join(r["pack"]).strip()
                # Only accept if it looks like a pack size (digits/digits + unit)
                if pack_re.match(pack_text):
                    current["pack"] = pack_text
                # If pack column is just a unit (e.g., "OZ"), try to combine with trailing qty in description
                elif re.fullmatch(r"(?:OZ|LB|G|KG)", pack_text, flags=re.IGNORECASE):
                    if current.get("description"):
                        m_qty_only = re.search(r"(\d+\/\d+(?:\.\d+)?)\b(?!\s*(?:OZ|LB|G|KG))", current["description"], flags=re.IGNORECASE)
                        if m_qty_only:
                            current["pack"] = f"{m_qty_only.group(1)} {pack_text.upper()}"
            if r["price"]:
                price_text = "".join(r["price"]).replace("$", "").strip()
                if number_re.match(price_text):
                    current["price"] = price_text
            if r["ext"]:
                ext_text = "".join(r["ext"]).replace("$", "").strip()
                if number_re.match(ext_text):
                    current["ext"] = ext_text

            # Fallback: Sometimes pack/price/ext appear together but land in unexpected buckets
            # Combine brand+desc first to preserve natural order like "... 12/5.99 OZ $95.88 $191.76"
            if not (current.get("pack") and current.get("price") and current.get("ext")):
                combined_triple = " ".join(
                    sum([
                        r.get("brand", []),
                        r.get("desc", []),
                        r.get("pack", []),
                        r.get("price", []),
                        r.get("ext", []),
                    ], [])
                )
                m_triple = pack_price_re.search(combined_triple)
                if m_triple:
                    if not current.get("pack"):
                        current["pack"] = m_triple.group("pack").strip()
                    if not current.get("price"):
                        current["price"] = m_triple.group("price").strip()
                    if not current.get("ext"):
                        current["ext"] = m_triple.group("ext").strip()

            try_flush()

        # Final attempt to flush any pending item at end of page
        try_flush()
        return items
