# Events Radar — recruiting events, competitions & hackathons for SWE / AI / quant students

Companion to Quant Radar. Same look, same workflow, but the rows are dated events:
firm insight programs and info sessions, trading & coding competitions, datathons,
hackathons, fellowships, winternships, conferences and career fairs — each with a date,
deadline, location/virtual, who it's for, and a **Register →** link.

Scope: US in-person + anything online.

## Publish it (one-time)

1. Create a new **public** GitHub repo (e.g. `Events_Radar`). Leave it empty.
2. Push this folder:

   ```bash
   cd ~/Events_Radar
   git init -b main
   git add .
   git commit -m "Events Radar"
   git remote add origin https://github.com/adadi-bit/Events_Radar.git
   git push -u origin main
   ```

   Pushing triggers the first scrape automatically (see the **Actions** tab).
3. **Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch `main`, folder `/docs` → Save.**
4. A minute later it's live at `https://adadi-bit.github.io/Events_Radar/`. It re-scrapes every 6 hours.

## Run it locally

```bash
cd ~/Events_Radar
python3 -m venv .venv && source .venv/bin/activate     # first time
pip install -r requirements.txt                       # first time
python3 main.py                # scrape, then open http://127.0.0.1:8000
python3 main.py --no-scrape    # just open the site
python3 scraper.py -v          # scrape only, per-source summary
```

## Where events come from

| Source | What | Dates |
|---|---|---|
| Devpost API | Open + upcoming hackathons (US / online) | Confirmed |
| MLH season schedule | Member hackathons (US / online), schema.org data | Confirmed |
| Curated list (`curated.py`) | ~65 recurring firm programs, competitions, conferences, fellowships (Jane Street INSIGHT/FTTP/ETC, Discover Citadel, Citadel Datathon/Terminal, SIG Discovery Days, D. E. Shaw fellowships, HRT & Virtu winternships, IMC Prosperity, WorldQuant IQC, Rotman ITC, Google STEP, Meta University, GHC, Tapia, TartanHacks…) | Confirmed when you supply `start`/`end`, otherwise **typical timing** (placed in its usual month, dashed date box). Every run re-fetches the page and upgrades to a real date/deadline when the page states one. |
| Firm event pages | Citadel, Jane Street, Optiver, IMC, SIG, HRT, Flow Traders, Google, JPMorgan, Goldman, Bloomberg | Confirmed — only links that sit next to a date are picked up; empty is normal when nothing is posted |
| GitHub list | `zapplyjobs/underclassmen-internships` (externships, insight series, fellowships, winternships) | Typical |

**Add an event**: append a `dict(...)` to `curated.py` (fields documented at the top) and push.
Confirmed dates on the page win over what you type, so you only need `month` for recurring things.

## Tags on every event

* **Type** — Hackathon, Competition, Insight program, Fellowship, Winternship, Firm event, Conference, Career fair
* **Track** — SWE, AI/ML, Quant, Finance (from the curated entry or inferred from the title)
* **Apply by …** — red deadline chip with days left (solid red when ≤ 7 days)
* **typical timing** — no confirmed date yet; the card says when it usually happens
* **New** — first seen in the last 3 days · **📅** downloads an .ics for confirmed dates

Tabs: Upcoming · Deadlines · Hackathons · Competitions · Programs · Conferences · Saved · Registered.
Saved / Registered / Hidden live in each viewer's browser. "Share view" copies the URL with your filters.

## Files

```
scraper.py    runs all sources, classifies, merges into events.db, writes docs/events.json
sources.py    Devpost, MLH, GitHub list, firm-page scanner, curated live-check
curated.py    the recurring-events list — edit this to add things
dates.py      date-range / deadline parsing for messy text
config.py     source URLs, hubs, track rules
db.py         SQLite state (first_seen / last_seen / active)
main.py       local runner
docs/         the site — served by GitHub Pages
.github/workflows/scrape.yml   6-hourly refresh
```
