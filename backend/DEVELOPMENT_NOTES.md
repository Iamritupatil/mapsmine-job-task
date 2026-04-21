# Development Notes

## Why Playwright
- Strong control over real browser automation.
- Reliable selectors, waits, and retries.
- Works with installed local Chrome via `channel=\"chrome\"`.

## How AI Was Used
- Planned modular backend architecture quickly.
- Generated fallback selector groups and parser patterns.
- Improved resilience patterns (retry, progress updates, safe parsing).

## Highest-Risk Fields
- `place_id` (not always directly exposed)
- `photo_count` (layout-dependent)
- `opening_hours` (often collapsed or dynamic)
- `top_review_1..3` (review section varies by listing type)

## Implemented Fallbacks
- Multiple selectors for core details (name/address/phone/website).
- URL + HTML parsing fallback for identifiers.
- Text-block parsing fallback for status/plus code/photo count.
- Continue-on-error extraction with logging and dedupe.
