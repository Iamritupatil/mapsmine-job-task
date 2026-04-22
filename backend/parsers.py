from __future__ import annotations

import json
import re
from typing import Iterable

from utils import clean_text, safe_int


def parse_rating_and_reviews(text: str) -> tuple[float | str, int | str]:
    if not text:
        return "", ""

    rating_match = re.search(r"(\d+(?:\.\d)?)\s", text)
    reviews_match = re.search(r"(\d[\d,]*)\s+reviews?", text, flags=re.IGNORECASE)

    rating: float | str = ""
    review_count: int | str = ""

    if rating_match:
        try:
            rating = float(rating_match.group(1))
        except ValueError:
            rating = ""

    if reviews_match:
        review_count = safe_int(reviews_match.group(1))

    return rating, review_count


def extract_plus_code(text_block: str) -> str:
    if not text_block:
        return ""
    match = re.search(r"\b[A-Z0-9]{4,}\+[A-Z0-9]{2,}\b", text_block)
    return match.group(0) if match else ""


def extract_open_status(text_block: str) -> str:
    if not text_block:
        return ""
    patterns = [
        r"Open[^\n\r]{0,60}",
        r"Closed[^\n\r]{0,60}",
        r"Opens[^\n\r]{0,60}",
        r"Temporarily closed[^\n\r]{0,60}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_block, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(0))
    return ""


def extract_photo_count(text_block: str) -> int | str:
    if not text_block:
        return ""
    match = re.search(r"(\d[\d,]*)\s+photos?", text_block, flags=re.IGNORECASE)
    return safe_int(match.group(1)) if match else ""


def normalize_hours(hours_items: Iterable[str]) -> str:
    lines = [clean_text(item) for item in hours_items if clean_text(item)]
    if not lines:
        return ""

    days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    result: dict[str, str] = {}
    pending_day: str | None = None

    for line in lines:
        if line.lower() in days:
            pending_day = line
        elif pending_day is not None:
            result[pending_day] = line
            pending_day = None
        else:
            result[line] = ""

    if result:
        return json.dumps(result, ensure_ascii=True)
    return json.dumps(lines, ensure_ascii=True)


def extract_possible_place_id_from_html(html: str) -> str:
    if not html:
        return ""
    patterns = [
        r'"place_id"\s*:\s*"([^"]+)"',
        r'"0x[0-9a-f]+:0x[0-9a-f]+"',
        r'!1s(0x[0-9a-f]+:0x[0-9a-f]+)',
        r'"cid"\s*:\s*"?(\d+)"?',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if not match:
            continue
        if match.groups():
            return clean_text(match.group(1))
        return clean_text(match.group(0).replace('"', ""))
    return ""


def extract_possible_place_id_from_url(url: str) -> str:
    if not url:
        return ""
    patterns = [
        r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)",
        r"cid=(\d+)",
        r"/place/([^/]+)/",
    ]
    for pattern in patterns:
        match = re.search(pattern, url, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""


def query_selector_any_text(page_or_locator, selectors: list[str]) -> str:
    for selector in selectors:
        try:
            node = page_or_locator.locator(selector).first
            if node.count() == 0:
                continue
            text = node.inner_text(timeout=1200)
            cleaned = clean_text(text)
            if cleaned:
                return cleaned
        except Exception:  # noqa: BLE001
            continue
    return ""
