from __future__ import annotations

import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Callable, TypeVar
from urllib.parse import parse_qs, unquote, urlparse

T = TypeVar("T")


def random_sleep(min_s: float = 0.8, max_s: float = 2.2) -> None:
    time.sleep(random.uniform(min_s, max_s))


def slugify(text: str, max_len: int = 80) -> str:
    cleaned = clean_text(text).lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")
    cleaned = cleaned[:max_len].strip("_")
    return cleaned or "scrape"


def build_output_basename(query: str, limit: int) -> str:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{slugify(query)}_{int(limit)}_{timestamp}"


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    # Google Maps often injects icon glyphs from Unicode Private Use Areas.
    # Strip them to keep extracted fields clean.
    cleaned = re.sub(r"[\uE000-\uF8FF]", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def safe_int(text: str | int | None) -> int | str:
    if text is None:
        return ""
    if isinstance(text, int):
        return text
    cleaned = re.sub(r"[^\d]", "", str(text))
    if not cleaned:
        return ""
    try:
        return int(cleaned)
    except ValueError:
        return ""


def safe_float(text: str | float | None) -> float | str:
    if text is None:
        return ""
    if isinstance(text, float):
        return text
    matched = re.search(r"-?\d+(?:\.\d+)?", str(text))
    if not matched:
        return ""
    try:
        return float(matched.group(0))
    except ValueError:
        return ""


def retry(func: Callable[[], T], attempts: int = 3, delay_s: float = 0.7) -> T:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(delay_s)
    if last_error:
        raise last_error
    raise RuntimeError("Retry failed without error.")


def parse_lat_lng_from_url(url: str) -> tuple[float | str, float | str]:
    def _extract(text: str) -> tuple[float | str, float | str]:
        if not text:
            return "", ""
        decoded = unquote(text)

        patterns = [
            r"@(-?\d{1,3}(?:\.\d+)?),(-?\d{1,3}(?:\.\d+)?)",
            r"!3d(-?\d{1,3}(?:\.\d+)?)!4d(-?\d{1,3}(?:\.\d+)?)",
            r"!4d(-?\d{1,3}(?:\.\d+)?)!3d(-?\d{1,3}(?:\.\d+)?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, decoded)
            if not match:
                continue
            lat = safe_float(match.group(1))
            lng = safe_float(match.group(2))
            if lat != "" and lng != "":
                return lat, lng
        return "", ""

    lat, lng = _extract(url)
    if lat != "" and lng != "":
        return lat, lng

    parsed = urlparse(url)

    query_params = parse_qs(parsed.query)
    ll = query_params.get("ll", [""])[0]
    if ll and "," in ll:
        parts = ll.split(",", 1)
        lat = safe_float(parts[0])
        lng = safe_float(parts[1])
        return lat, lng

    return "", ""


def normalize_website_url(url: str | None) -> str:
    if not url:
        return ""

    cleaned = clean_text(url)
    if not cleaned:
        return ""

    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    if cleaned.startswith("/"):
        cleaned = f"https://www.google.com{cleaned}"

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        return ""

    # Google often wraps outbound links with /url?url=... or /url?q=...
    if parsed.netloc.endswith("google.com") and parsed.path == "/url":
        qs = parse_qs(parsed.query)
        candidate = (qs.get("url", [""])[0] or qs.get("q", [""])[0]).strip()
        candidate = unquote(candidate)
        if candidate.startswith(("http://", "https://")):
            cleaned = candidate
            parsed = urlparse(cleaned)

    # Never report Google Maps URLs as "business website".
    if parsed.netloc.endswith("google.com") and parsed.path.startswith("/maps"):
        return ""

    return cleaned


def maybe_extract_price_level(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"\${1,4}", text)
    return match.group(0) if match else ""


def setup_logger() -> logging.Logger:
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("mapsmine.backend")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_dir / "scraper.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def normalize_for_dedupe(value: Any) -> str:
    return clean_text(str(value)).lower()
