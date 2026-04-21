# MapsMine — Google Maps Scraper

A Python-based Google Maps scraper using real Chrome browser automation (Playwright). No paid APIs. No third-party scraping services. Extracts 50+ business listings per run and exports clean Excel/CSV files.

Built with a FastAPI backend and an optional React + Vite frontend UI.

---

## What It Extracts

Every listing captures all 15 required fields:

| Field | Description |
|---|---|
| `business_name` | Name of the business |
| `category` | Business category (e.g. "HVAC contractor") |
| `full_address` | Street address |
| `phone_number` | Contact phone number |
| `website` | Business website URL |
| `rating` | Star rating (e.g. 4.7) |
| `review_count` | Total number of reviews |
| `price_level` | Price indicator (`$` – `$$$$`) if shown |
| `plus_code` | Google Plus Code (e.g. `7HQX+8F Dubai`) |
| `latitude` | Latitude parsed from Maps URL |
| `longitude` | Longitude parsed from Maps URL |
| `place_id` | Google Place ID (extracted from page HTML/URL) |
| `opening_hours` | Full weekly schedule as JSON |
| `open_closed_status` | Current open/closed status |
| `photo_count` | Number of photos on the listing |
| `top_review_1/2/3` | Top 3 review text snippets |
| `google_maps_url` | Direct URL to the Maps listing |

---

## Project Structure

```
task/
├── backend/
│   ├── main.py           # FastAPI app with job queue and download endpoints
│   ├── scraper.py        # Core Playwright scraper (GoogleMapsScraper class)
│   ├── parsers.py        # Field extraction helpers (ratings, hours, place ID, etc.)
│   ├── models.py         # BusinessRow dataclass + OUTPUT_COLUMNS
│   ├── utils.py          # Text cleaning, URL parsing, retry logic, logger
│   ├── run_scrape.py     # CLI entry point (no API needed)
│   ├── requirements.txt
│   ├── Dockerfile        # For Railway / Render deployment
│   └── sample_output/
│       └── ac_repair_services_dubai_50.xlsx   ← real test run, 50 rows
└── frontend/
    ├── App.jsx           # React UI (search box, progress, export)
    ├── main.jsx
    ├── index.html
    ├── vite.config.js
    └── package.json
```

---

## Quickstart

### Requirements

- Python 3.10+
- Google Chrome installed on your machine
- Node.js 18+ (only for the frontend UI)

### 1 — Backend setup

From the repo root:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r backend/requirements.txt
playwright install
```

### 2 — Run as a CLI script (simplest)

```bash
cd backend

python run_scrape.py \
  --query "AC repair services in Dubai" \
  --limit 50 \
  --format xlsx \
  --headless \
  --workers 5
```

Output is saved to `backend/output/` with an auto-generated filename like:
```
ac_repair_services_in_dubai_50_20260421_163358.xlsx
```

**CLI options:**

| Flag | Default | Description |
|---|---|---|
| `--query` | required | Search query (e.g. `"gyms in Abu Dhabi"`) |
| `--limit` | 50 | Number of listings to extract (1–500) |
| `--format` | xlsx | Output format: `xlsx` or `csv` |
| `--headless` | off | Run Chrome in background (no visible window) |
| `--workers` | 5 | Parallel Chrome workers (1–10). Higher = faster, higher block risk |
| `--out` | auto | Custom output path |

### 3 — Run as an API server

```bash
cd backend
uvicorn main:app --host 127.0.0.1 --port 8000
```

> **Windows note:** Do not use `--reload`. Uvicorn's reload mode conflicts with Playwright's event loop policy on Windows.

**POST `/scrape`** — start a job:
```json
{
  "query": "AC repair services in Dubai",
  "limit": 50,
  "headless": true,
  "workers": 5,
  "format": "xlsx"
}
```

**GET `/scrape/{job_id}`** — poll status + progress

**GET `/scrape/{job_id}/download`** — download the result file

**GET `/health`** — health check

### 4 — Frontend UI (optional)

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The UI connects to the FastAPI backend at `http://localhost:8000` by default.

---

## Sample Output

`backend/sample_output/ac_repair_services_dubai_50.xlsx`

A real test run of 50 AC repair listings in Dubai. Includes all 17 columns with business names, categories, phone numbers, addresses, ratings, hours, coordinates, and review snippets.

---

## How Block-Resistance Works

- **Random delays** between every request (`random_sleep`) — mimics human pacing
- **Real Chrome** via `channel="chrome"` — not a detectable headless binary
- **Anti-automation flag disabled** (`--disable-blink-features=AutomationControlled`)
- **Realistic User-Agent** and viewport set on every context
- **Consent screen handling** — auto-dismisses Google consent popups across regions
- **Retry logic** on listing navigation (3 attempts with backoff)
- **Parallel workers** are configurable — lower workers = lower detection risk

---

## Deployment

**Frontend → Vercel**
Import the repo on Vercel. `vercel.json` at the root already configures it to build from `frontend/`. Add env variable `VITE_API_BASE=https://your-backend-url` in Vercel settings.

**Backend → Railway**
Connect the repo, set the root directory to `backend/`. Railway detects the `Dockerfile` and builds it automatically (installs Chrome + Python deps).

---

## How I Used Claude / AI During Development

Claude (Claude Code) was my primary development assistant throughout this project. Here's specifically how:

- **Architecture decisions** — I described the requirements and Claude recommended splitting the scraper into `scraper.py`, `parsers.py`, `utils.py`, and `models.py` rather than a monolithic script. This made each concern testable in isolation.

- **Selector design and fallbacks** — Google Maps has no stable CSS class names. Claude helped design multi-candidate selector lists (e.g. trying 4–5 selectors per field in priority order) so that if Google changes one selector, the others still catch the data.

- **Parser logic** — Claude wrote the regex-based parsers for extracting coordinates from Maps URLs (`@lat,lng` and `!3d...!4d...` patterns), Plus Codes, place IDs from both URL and raw HTML, and rating/review count parsing from messy mixed text.

- **Parallel worker architecture** — Claude designed the `ThreadPoolExecutor` pattern in `GoogleMapsScraper.run()` where the collector browser does the search and scroll, then closes itself before spawning N worker sub-scrapers that each get a chunk of URLs. This avoids race conditions on shared browser state.

- **Deployment config** — Claude generated the `Dockerfile` (Chrome install via apt + Playwright deps), `vercel.json`, and `.gitignore` based on the project structure.

- **Debugging edge cases** — I described issues like consent popups in UAE regions and Windows event loop errors with Playwright. Claude identified the root causes and added `asyncio.WindowsProactorEventLoopPolicy` and frame-level consent button scanning as fixes.

The workflow was conversational: I'd describe what I needed or paste an error, Claude would generate the code or explain the fix, and I'd test and iterate. Roughly 70–80% of the codebase was written or significantly shaped by Claude, with my role being architecture review, testing, and integration decisions.
