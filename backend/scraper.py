from __future__ import annotations

import asyncio
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import Callable

import pandas as pd
from playwright.sync_api import BrowserContext, Locator, Page, Playwright, sync_playwright

from models import BusinessRow, OUTPUT_COLUMNS
from parsers import (
    extract_open_status,
    extract_photo_count,
    extract_plus_code,
    extract_possible_place_id_from_html,
    extract_possible_place_id_from_url,
    normalize_hours,
    parse_rating_and_reviews,
    query_selector_any_text,
)
from utils import (
    clean_text,
    maybe_extract_price_level,
    normalize_for_dedupe,
    normalize_website_url,
    parse_lat_lng_from_url,
    random_sleep,
    retry,
    safe_float,
    setup_logger,
)


_STEALTH_SCRIPT = """
(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
    const orig = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = (p) =>
        p.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : orig(p);
})();
"""

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class GoogleMapsScraper:
    def __init__(
        self,
        query: str,
        limit: int,
        headless: bool,
        output_path: str,
        timeout: int = 45000,
        slow_mode: int = 0,
        workers: int = 1,
        proxy: str | None = None,
    ) -> None:
        self.query = query
        self.limit = max(1, limit)
        self.headless = headless
        self.output_path = str(output_path)
        self.timeout = timeout
        self.slow_mode = slow_mode
        self.workers = max(1, min(int(workers), 10))
        self.proxy = proxy

        self.logger = setup_logger()
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

        self.rows: list[BusinessRow] = []
        self.unique_listing_keys: set[str] = set()
        self.unique_result_urls: list[str] = []

    def start_browser(self) -> None:
        if sys.platform == "win32":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception:  # noqa: BLE001
                pass

        self.playwright = sync_playwright().start()
        args = [
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-gpu",
        ]

        try:
            browser = self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mode,
                args=args,
            )
        except Exception as exc:  # noqa: BLE001
            self.playwright.stop()
            raise RuntimeError(
                "Could not launch Chromium. Run: playwright install chromium"
            ) from exc

        viewport_w = random.randint(1440, 1600)
        viewport_h = random.randint(860, 960)
        proxy_config = {"server": self.proxy} if self.proxy else None

        self.context = browser.new_context(
            viewport={"width": viewport_w, "height": viewport_h},
            locale="en-US",
            timezone_id="America/New_York",
            user_agent=random.choice(_USER_AGENTS),
            proxy=proxy_config,
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            },
        )
        self.context.add_init_script(_STEALTH_SCRIPT)
        self.page = self.context.new_page()
        self.page.set_default_timeout(self.timeout)

    def _warm_up_maps(self) -> None:
        if not self.page:
            return
        try:
            self.page.goto("https://www.google.com/maps", wait_until="domcontentloaded")
            self.page.wait_for_timeout(900)
            self.maybe_accept_consent()
        except Exception:  # noqa: BLE001
            return

    def maybe_accept_consent(self) -> None:
        if not self.page:
            return

        consent_button_selectors = [
            'button#L2AGLb',
            'button:has-text("Accept all")',
            'button:has-text("I agree")',
            'button:has-text("Agree")',
            'button:has-text("Accept")',
            'button[aria-label="Accept all"]',
            'button[aria-label="I agree"]',
        ]

        def _try_click(container) -> bool:
            for selector in consent_button_selectors:
                try:
                    button = container.locator(selector).first
                    if button.count() == 0:
                        continue
                    button.wait_for(state="visible", timeout=2500)
                    button.click(timeout=2500)
                    return True
                except Exception:  # noqa: BLE001
                    continue
            return False

        if _try_click(self.page):
            self.page.wait_for_timeout(800)
            return

        for frame in self.page.frames:
            if frame == self.page.main_frame:
                continue
            if _try_click(frame):
                self.page.wait_for_timeout(800)
                return

    def search(self) -> None:
        if not self.page:
            raise RuntimeError("Browser page is not initialized.")

        # Navigate directly to search URL — bypasses search box interaction
        # and avoids consent/redirect issues on server IPs.
        from urllib.parse import quote_plus
        direct_url = f"https://www.google.com/maps/search/{quote_plus(self.query)}/?hl=en&gl=us"
        self.page.goto(direct_url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(2000)

        for _ in range(3):
            self.maybe_accept_consent()
            current_url = self.page.url or ""
            if any(token in current_url for token in ["consent.google.com", "/sorry/"]):
                self.page.wait_for_timeout(1500)
                self.page.goto(direct_url, wait_until="domcontentloaded")
                self.page.wait_for_timeout(2000)
                continue
            break

        self.wait_for_results_feed()

    def wait_for_results_feed(self) -> Locator:
        if not self.page:
            raise RuntimeError("Page is not initialized.")

        feed_selectors = [
            'div[role="feed"]',
            'div[aria-label*="Results for"]',
            'div[aria-label*="results"]',
            'div[jsaction*="pane.resultSection"]',
            '#section-search-results',
        ]

        for selector in feed_selectors:
            node = self.page.locator(selector).first
            try:
                node.wait_for(timeout=15000)
                return node
            except Exception:  # noqa: BLE001
                continue

        raise RuntimeError("Results panel/feed was not found.")

    def collect_result_cards(self) -> int:
        if not self.page:
            return 0

        href_candidates = self.page.locator('a[href*="/maps/place"]').all()
        for anchor in href_candidates:
            try:
                href = clean_text(anchor.get_attribute("href"))
                if not href:
                    continue
                full_url = href if href.startswith("http") else f"https://www.google.com{href}"
                if full_url not in self.unique_result_urls:
                    self.unique_result_urls.append(full_url)
            except Exception:  # noqa: BLE001
                continue
        return len(self.unique_result_urls)

    def scroll_results_panel_until_enough(self) -> None:
        if not self.page:
            raise RuntimeError("Page is not initialized.")

        feed = self.wait_for_results_feed()
        stagnant_scrolls = 0
        previous_count = 0

        while len(self.unique_result_urls) < self.limit and stagnant_scrolls < 8:
            current_count = self.collect_result_cards()
            self.logger.info("Collected %s candidate result URLs", current_count)

            if current_count <= previous_count:
                stagnant_scrolls += 1
            else:
                stagnant_scrolls = 0
            previous_count = current_count

            try:
                feed.evaluate("el => { el.scrollBy(0, el.clientHeight * 0.85); }")
            except Exception:  # noqa: BLE001
                self.page.mouse.wheel(0, 2200)

            random_sleep(0.8, 1.5)

    def open_listing(self, url: str) -> None:
        if not self.page:
            raise RuntimeError("Page is not initialized.")

        def _go() -> None:
            self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
            self.page.wait_for_timeout(900)
            self.maybe_accept_consent()

            current_url = self.page.url or ""
            if any(token in current_url for token in ["consent.google.com", "/sorry/"]):
                self.page.goto("https://www.google.com/maps", wait_until="domcontentloaded")
                self.page.wait_for_timeout(900)
                self.maybe_accept_consent()
                self.page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                self.page.wait_for_timeout(900)

        retry(_go, attempts=3)

    def extract_top_reviews(self) -> tuple[str, str, str]:
        if not self.page:
            return "", "", ""

        review_texts: list[str] = []
        review_open_selectors = [
            'button[aria-label*="reviews"]',
            'button:has-text("reviews")',
            'button:has-text("Reviews")',
        ]

        for selector in review_open_selectors:
            try:
                btn = self.page.locator(selector).first
                if btn.count() > 0:
                    btn.click(timeout=1200)
                    self.page.wait_for_timeout(1100)
                    break
            except Exception:  # noqa: BLE001
                continue

        snippet_selectors = [
            'div[data-review-id] span[jsname="bN97Pc"]',
            'div[aria-label*="stars"] ~ span',
            'span.wiI7pd',
        ]

        for selector in snippet_selectors:
            try:
                items = self.page.locator(selector).all()
                for item in items:
                    txt = clean_text(item.inner_text(timeout=800))
                    if txt and txt not in review_texts:
                        review_texts.append(txt)
                    if len(review_texts) >= 3:
                        return tuple((review_texts + ["", "", ""])[:3])
            except Exception:  # noqa: BLE001
                continue

        return tuple((review_texts + ["", "", ""])[:3])

    def extract_hours(self) -> str:
        if not self.page:
            return ""

        open_hours_btn_selectors = [
            'button[aria-label*="hours"]',
            'button:has-text("Hours")',
            'button:has-text("Open")',
        ]

        for selector in open_hours_btn_selectors:
            try:
                btn = self.page.locator(selector).first
                if btn.count() > 0:
                    btn.click(timeout=1200)
                    self.page.wait_for_timeout(500)
                    break
            except Exception:  # noqa: BLE001
                continue

        hour_row_selectors = [
            'table tr',
            'div[role="main"] div:has-text("Monday")',
            'div[role="main"] div:has-text("Tuesday")',
            'div[role="main"] div:has-text("Wednesday")',
            'div[role="main"] div:has-text("Thursday")',
            'div[role="main"] div:has-text("Friday")',
            'div[role="main"] div:has-text("Saturday")',
            'div[role="main"] div:has-text("Sunday")',
        ]

        rows: list[str] = []
        for selector in hour_row_selectors:
            try:
                nodes = self.page.locator(selector).all()
                for node in nodes:
                    txt = clean_text(node.inner_text(timeout=400))
                    if txt and txt not in rows:
                        rows.append(txt)
            except Exception:  # noqa: BLE001
                continue

        return normalize_hours(rows)

    def extract_listing_details(self) -> BusinessRow:
        if not self.page:
            return BusinessRow()

        self.page.wait_for_timeout(900)

        raw_text = self.page.locator("body").inner_text(timeout=2500)
        main_text = clean_text(raw_text)
        page_url = self.page.url
        page_html = self.page.content()

        business_name = query_selector_any_text(self.page, [
            "h1",
            'h1[class*="fontHeadlineLarge"]',
            'div[role="main"] h1',
        ])

        category = query_selector_any_text(self.page, [
            'button[jsaction$=".category"]',
            'button[jsaction*=".category"]',
            'button[jsaction*="pane.rating.category"]',
            'button[aria-label*="Category"]',
        ])

        full_address = query_selector_any_text(self.page, [
            'button[data-item-id="address"]',
            'button[aria-label*="Address"]',
            'button[aria-label*="address"]',
        ])

        phone_number = query_selector_any_text(self.page, [
            'button[data-item-id*="phone"]',
            'button[aria-label^="Phone"]',
            'button[aria-label*="Call"]',
        ])

        website = ""
        website_selectors = [
            'a[data-item-id="authority"]',
            'a[data-item-id*="authority"]',
            'a[aria-label*="Website"]',
        ]
        for selector in website_selectors:
            try:
                node = self.page.locator(selector).first
                if node.count() == 0:
                    continue
                href = clean_text(node.get_attribute("href"))
                if href:
                    website = normalize_website_url(href)
                    break
            except Exception:  # noqa: BLE001
                continue

        rating_text = query_selector_any_text(self.page, [
            'div[role="main"] span[aria-hidden="true"]',
            'div[role="main"] div:has-text("reviews")',
            'div[role="main"] span:has-text("reviews")',
        ])
        rating, review_count = parse_rating_and_reviews(rating_text)

        open_closed_status = extract_open_status(raw_text)
        plus_code = extract_plus_code(raw_text)
        price_level = maybe_extract_price_level(category or main_text)
        latitude, longitude = parse_lat_lng_from_url(page_url)

        place_id = extract_possible_place_id_from_url(page_url)
        if not place_id:
            place_id = extract_possible_place_id_from_html(page_html)

        opening_hours = self.extract_hours()
        photo_count = extract_photo_count(raw_text)

        top_review_1, top_review_2, top_review_3 = self.extract_top_reviews()

        row = BusinessRow(
            business_name=business_name,
            category=category,
            full_address=full_address,
            phone_number=phone_number,
            website=website,
            rating=safe_float(str(rating)) if rating != "" else "",
            review_count=review_count,
            price_level=price_level,
            plus_code=plus_code,
            latitude=latitude,
            longitude=longitude,
            place_id=place_id,
            opening_hours=opening_hours,
            open_closed_status=open_closed_status,
            photo_count=photo_count,
            top_review_1=top_review_1,
            top_review_2=top_review_2,
            top_review_3=top_review_3,
            google_maps_url=page_url,
        )
        return row

    def _scrape_url_chunk(
        self,
        urls: list[str],
        on_row: Callable[[], None] | None = None,
    ) -> list[BusinessRow]:
        self.start_browser()
        self._warm_up_maps()

        for url in urls:
            try:
                self.open_listing(url)
                row = self.extract_listing_details()

                row_key = self._build_row_key(row)
                if row_key in self.unique_listing_keys:
                    continue

                self.unique_listing_keys.add(row_key)
                self.rows.append(row)
                if on_row:
                    on_row()
                self.logger.info("Scraped %s/%s: %s", len(self.rows), len(urls), row.business_name)
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("Failed to extract %s due to %s", url, exc)
            finally:
                random_sleep(0.15, 0.55)

        return self.rows

    def _build_row_key(self, row: BusinessRow) -> str:
        if row.google_maps_url:
            return normalize_for_dedupe(row.google_maps_url)
        return f"{normalize_for_dedupe(row.business_name)}|{normalize_for_dedupe(row.full_address)}"

    def run(self, progress_callback: Callable[[int, int], None] | None = None) -> list[BusinessRow]:
        self.start_browser()
        self.search()
        self.scroll_results_panel_until_enough()

        target_urls = self.unique_result_urls[: self.limit]
        self.logger.info("Beginning extraction for %s listings", len(target_urls))

        if self.workers > 1 and len(target_urls) > 1:
            # Free the collector browser before launching multiple worker browsers.
            self.close()

            progress_lock = Lock()
            processed = 0

            def on_row() -> None:
                nonlocal processed
                with progress_lock:
                    processed += 1
                    current = processed
                if progress_callback:
                    progress_callback(current, self.limit)

            chunks = [target_urls[i:: self.workers] for i in range(self.workers)]
            chunks = [chunk for chunk in chunks if chunk]

            combined_rows: list[BusinessRow] = []

            def worker(chunk: list[str]) -> list[BusinessRow]:
                worker_scraper = GoogleMapsScraper(
                    query=self.query,
                    limit=len(chunk),
                    headless=self.headless,
                    output_path=self.output_path,
                    timeout=self.timeout,
                    slow_mode=0,
                    workers=1,
                    proxy=self.proxy,
                )
                try:
                    return worker_scraper._scrape_url_chunk(chunk, on_row=on_row)
                finally:
                    worker_scraper.close()

            with ThreadPoolExecutor(max_workers=len(chunks)) as pool:
                futures = [pool.submit(worker, chunk) for chunk in chunks]
                for future in as_completed(futures):
                    try:
                        combined_rows.extend(future.result())
                    except Exception as exc:  # noqa: BLE001
                        self.logger.exception("Worker failed: %s", exc)

            # Deduplicate across workers with stable key preference.
            unique_keys: set[str] = set()
            deduped: list[BusinessRow] = []
            for row in combined_rows:
                row_key = self._build_row_key(row)
                if row_key in unique_keys:
                    continue
                unique_keys.add(row_key)
                deduped.append(row)
                if len(deduped) >= self.limit:
                    break

            self.rows = deduped
            return self.rows

        for index, url in enumerate(target_urls, start=1):
            try:
                self.open_listing(url)
                row = self.extract_listing_details()

                row_key = self._build_row_key(row)
                if row_key in self.unique_listing_keys:
                    continue

                self.unique_listing_keys.add(row_key)
                self.rows.append(row)
                self.logger.info("Scraped %s/%s: %s", len(self.rows), self.limit, row.business_name)
            except Exception as exc:  # noqa: BLE001
                self.logger.exception("Failed to extract %s due to %s", url, exc)
            finally:
                if progress_callback:
                    progress_callback(len(self.rows), self.limit)
                random_sleep(0.25, 0.8)

            if len(self.rows) >= self.limit:
                break

        return self.rows

    def to_dataframe(self) -> pd.DataFrame:
        records = [asdict(row) for row in self.rows]
        df = pd.DataFrame(records)
        if df.empty:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        for col in OUTPUT_COLUMNS:
            if col not in df.columns:
                df[col] = ""

        # Deduplicate with stable key preference.
        df["_dedupe_key"] = df.apply(
            lambda r: normalize_for_dedupe(r.get("google_maps_url", ""))
            or f"{normalize_for_dedupe(r.get('business_name', ''))}|{normalize_for_dedupe(r.get('full_address', ''))}",
            axis=1,
        )
        df = df.drop_duplicates(subset=["_dedupe_key"]).drop(columns=["_dedupe_key"])

        # Normalize whitespace.
        for col in OUTPUT_COLUMNS:
            df[col] = df[col].apply(lambda x: clean_text(str(x)) if x is not None else "")

        # Keep numerics clean where parseable.
        for col in ["rating", "latitude", "longitude"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["review_count"] = pd.to_numeric(df["review_count"], errors="coerce").astype("Int64")
        df["photo_count"] = pd.to_numeric(df["photo_count"], errors="coerce").astype("Int64")

        return df[OUTPUT_COLUMNS]

    def save_output(self) -> Path:
        output = Path(self.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        df = self.to_dataframe()

        ext = output.suffix.lower()
        if ext == ".csv":
            df.to_csv(output, index=False, encoding="utf-8-sig")
        elif ext == ".xlsx":
            df.to_excel(output, index=False)
        else:
            raise ValueError("Unsupported output extension. Use .csv or .xlsx")

        return output

    def close(self) -> None:
        try:
            if self.context:
                try:
                    self.context.close()
                except Exception:  # noqa: BLE001
                    pass
        finally:
            if self.playwright:
                try:
                    self.playwright.stop()
                except Exception:  # noqa: BLE001
                    pass

        self.page = None
        self.context = None
        self.playwright = None
