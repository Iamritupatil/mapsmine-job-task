from __future__ import annotations

import argparse
from pathlib import Path

from scraper import GoogleMapsScraper
from utils import build_output_basename


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Google Maps scrape and export CSV/XLSX")
    parser.add_argument("--query", required=True, help='Search query, e.g. "AC repair services in Dubai"')
    parser.add_argument("--limit", type=int, default=50, help="Number of listings to extract (1-500)")
    parser.add_argument("--format", choices=["csv", "xlsx"], default="xlsx", help="Output format")
    parser.add_argument("--headless", action="store_true", help="Run Chrome headless")
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Parallel Chrome workers (1-10). Higher is faster but increases block risk.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path. Defaults to backend/output/<query>_<limit>_<timestamp>.<format>",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    base_dir = Path(__file__).resolve().parent
    output_dir = base_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = output_dir / f"{build_output_basename(args.query, args.limit)}.{args.format}"

    if out_path.suffix.lower() not in {".csv", ".xlsx"}:
        out_path = out_path.with_suffix(f".{args.format}")

    scraper = GoogleMapsScraper(
        query=args.query,
        limit=max(1, min(int(args.limit), 500)),
        headless=bool(args.headless),
        output_path=str(out_path),
        workers=max(1, min(int(args.workers), 10)),
    )

    try:
        rows = scraper.run()
        saved_path = scraper.save_output()
    finally:
        scraper.close()

    print(f"Saved {len(rows)} rows to {saved_path}")


if __name__ == "__main__":
    main()
