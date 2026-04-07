# outfit_extractor.py
import re

TOP_TYPES    = ["shirt", "t-shirt", "tshirt", "kurta", "blouse", "jacket",
                "top", "sweater", "hoodie", "polo", "tunic"]
BOTTOM_TYPES = ["jeans", "trouser", "pant", "skirt", "shorts",
                "leggings", "chinos", "palazzos", "cargo"]
SHOE_TYPES   = ["sneaker", "loafer", "heel", "sandal", "boot",
                "slipper", "moccasin", "oxford", "flat", "shoes"]
ACC_TYPES    = ["watch", "belt", "cap", "bag", "scarf", "bracelet",
                "necklace", "sunglasses", "hat", "purse", "jacket"]  # jacket as accessory layer

# Placeholders the LLM uses when it doesn't know — ignore these
INVALID_NAMES = {"your shoes", "your top", "your bottom", "your shirt",
                 "your pants", "your jeans", "your outfit"}

COLORS = ["dark brown", "light blue", "dark blue", "navy blue", "light grey",
          "dark grey", "red", "blue", "green", "black", "white", "grey", "gray",
          "navy", "brown", "beige", "pink", "yellow", "purple", "orange",
          "maroon", "olive", "cream", "teal", "cyan", "khaki", "denim"]

STYLES = ["slim fit", "straight fit", "flared", "high waist", "oversized",
          "crop", "full sleeve", "half sleeve", "sleeveless", "lace-up",
          "slip-on", "ankle length", "chunky", "running", "sports",
          "striped", "polo", "cargo", "relaxed", "ripped", "formal", "denim"]


def _detect(text: str, keywords: list) -> str | None:
    for kw in keywords:
        if kw in text:
            return kw
    return None


def _extract_color(text: str) -> str | None:
    # Sort by length descending so "navy blue" matches before "blue"
    for c in sorted(COLORS, key=len, reverse=True):
        if c in text:
            return c
    return None


def _extract_style(text: str) -> str | None:
    for s in sorted(STYLES, key=len, reverse=True):
        if s in text:
            return s
    return None


def _make_item(text: str, keywords: list) -> dict | None:
    # Reject LLM placeholder names
    if text.strip().lower() in INVALID_NAMES:
        return None
    return {
        "name":  text.strip(),
        "type":  _detect(text, keywords),
        "color": _extract_color(text),
        "style": _extract_style(text),
    }


def _empty_accessory() -> dict:
    return {"name": None, "type": None, "color": None, "style": None}


def _get_segments(block: str) -> list[str]:
    """
    Handles single-line format:
    'navy blue formal shirt + light blue jeans + blue denim jacket + your shoes. reason'
    Splits on '+', strips reason text after last '.'.
    """
    # Remove everything after the first period (the "why" sentence)
    block = block.split('.')[0]

    # Strip markdown/bullet/emoji prefixes
    block = re.sub(r'^[-•*🔹👔👗👟👞💼🧥]+\s*', '', block).strip()
    block = re.sub(r'\*+', '', block).strip()

    # Split on '+' or ',' 
    if '+' in block:
        parts = [p.strip() for p in block.split('+') if p.strip()]
    else:
        parts = [p.strip() for p in block.split(',') if p.strip()]

    return parts


def extract_outfits(answer: str) -> list:
    # Don't parse the off-topic fallback response
    if "that's outside my lane" in answer.lower():
        return []

    answer = answer.lower()

    # Split on "outfit 1 / 2 / 3" headings
    blocks = re.split(r'outfit\s*[#\-–:]?\s*\d+', answer)
    if len(blocks) > 1:
        blocks = blocks[1:]

    outfits = []
    for i, block in enumerate(blocks[:3]):
        # Strip the vibe label before the colon e.g. "– relaxed: ..."
        block_body = re.sub(r'^[^:]*:\s*', '', block.strip())

        segments = _get_segments(block_body)

        top = bottom = shoes = accessory = None

        for seg in segments:
            # Jackets after a top is already found → treat as accessory layer
            if not top and _detect(seg, TOP_TYPES) and "jacket" not in seg:
                top = _make_item(seg, TOP_TYPES)
            elif not bottom and _detect(seg, BOTTOM_TYPES):
                bottom = _make_item(seg, BOTTOM_TYPES)
            elif not shoes and _detect(seg, SHOE_TYPES):
                shoes = _make_item(seg, SHOE_TYPES)  # returns None if placeholder
            elif not accessory and (
                _detect(seg, ACC_TYPES) or "jacket" in seg
            ):
                accessory = _make_item(seg, ACC_TYPES)

        occasion_match = re.search(
            r'(casual|formal|party|office|work|date night|festive|beach|ethnic|western|smart casual|active casual|sporty|street|relaxed|evening)',
            block[:200]
        )
        occasion = occasion_match.group(1).capitalize() if occasion_match else "Casual"

        outfits.append({
            "outfit_number": i + 1,
            "occasion":      occasion,
            "top":           top,
            "bottom":        bottom,
            "shoes":         shoes,   # None if LLM used a placeholder
            "accessory":     accessory if accessory else _empty_accessory(),
        })

    return outfits
