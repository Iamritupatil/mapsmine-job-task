# MapsMine Backend

Production-oriented Google Maps scraper backend with real browser automation (Playwright + local Chrome), job polling, and CSV/XLSX export.

## What It Does
- Starts scrape jobs from a query + listing limit.
- Uses real Chrome automation on Google Maps (no Places API, no paid scraping API).
- Tracks job status and progress.
- Exposes download endpoint for result files.

## Requirements
- Python 3.10+
- Google Chrome installed locally
- Windows/macOS/Linux supported by Playwright

## Setup
1. Create + activate a virtualenv (recommended at repo root):
  - From repo root: `python -m venv .venv`
  - Windows PowerShell: `\.venv\Scripts\Activate.ps1`
2. Install dependencies:
  - `pip install -r backend/requirements.txt`
3. Install Playwright browser dependencies:
  - `python -m playwright install`

## Run API
From `backend/`:

`uvicorn main:app --host 127.0.0.1 --port 8000`

Note (Windows): avoid `--reload` with Playwright jobs. Uvicorn reload uses a subprocess-friendly event loop policy that can break Playwright on some Windows setups.

## Run as Script (CLI)
From `backend/`:

`python run_scrape.py --query "AC repair services in Dubai" --limit 50 --format xlsx --headless --workers 5`

Outputs are saved under `backend/output/` by default with a query-based name like:

`ac_repair_services_in_dubai_50_20260421_153012.xlsx`

## Sample Output
- `backend/sample_output/ac_repair_services_dubai_50.xlsx` (50 rows, generated from a real run)

## Endpoints
### POST `/scrape`
Body:
```json
{
  "query": "restaurants in Dubai",
  "limit": 50,
  "headless": true,
  "workers": 5,
  "format": "xlsx"
}
```

Response:
```json
{
  "job_id": "uuid-string",
  "status": "queued"
}
```

### GET `/scrape/{job_id}`
Returns queued/running/completed/failed with progress and result metadata.

### GET `/scrape/{job_id}/download`
Downloads final CSV/XLSX.

## Known Limitations
- Google Maps DOM changes can break selectors.
- Some listings do not expose all fields in DOM.
- `place_id` and `photo_count` are best-effort and depend on page exposure.
- Higher `workers` is faster but increases the risk of blocks/CAPTCHA from Google Maps.

## Ethical/Legal Note
For personal evaluation/demo usage. Review Google terms and all applicable local laws before production deployment.

## AI Usage Note
AI assistance was used to accelerate architecture planning, fallback selector design, parser logic, and error handling improvements.
