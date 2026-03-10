# NHL Fantasy Optimizer

Weekly salary-cap fantasy hockey lineup optimizer. Wraps the existing PuLP/pandas optimizer in a FastAPI + React web app.
<img width="1189" height="1297" alt="image" src="https://github.com/user-attachments/assets/8f1bd522-a4b3-42ce-be4a-8bb05c77f349" />


## Local Development

### Prerequisites

- Node.js 20+ with pnpm
- Python 3.12+ (uv recommended for venv management)

### Setup

```bash
# Frontend dependencies
pnpm install

# Python backend (one-time setup)
uv venv .venv
uv pip install -r requirements.txt
```

### Running

Open two terminals:

```bash
# Terminal 1: Frontend (Vite dev server on :5173)
pnpm dev

# Terminal 2: Backend (FastAPI on :8000)
pnpm dev:api
```

Open http://localhost:5173. Default password is `dev`.

The Vite dev server proxies `/api/*` requests to the FastAPI backend automatically.

### Environment Variables (optional for local dev)

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PASSWORD` | `dev` | Login password |
| `SECRET_KEY` | `dev-secret-key-change-in-production` | HMAC signing key for session cookies |
| `ENVIRONMENT` | `development` | Set to `production` for secure cookies |
| `DATA_DIR` | `data` | SQLite database directory |

## Railway Deployment

The app deploys as a single Docker container. Railway auto-detects the `Dockerfile`.

### Steps

1. Push the repo to GitHub
2. Create a new Railway project, connect the GitHub repo
3. Railway will auto-detect the Dockerfile and build
4. Add environment variables in Railway dashboard:
   - `APP_PASSWORD` — set to your desired login password
   - `SECRET_KEY` — set to a random high-entropy string (e.g., `openssl rand -hex 32`)
   - `ENVIRONMENT` — set to `production`
5. Add a persistent volume mounted at `/app/data` (for SQLite persistence across deploys)
6. Deploy

Railway provides the `PORT` env var automatically. The health check endpoint is `GET /api/health`.

### What the Docker build does

1. **Stage 1 (Node):** Installs frontend deps, runs `pnpm build` to produce `dist/`
2. **Stage 2 (Python):** Installs backend deps, copies `server/`, `seed_data/`, and built `dist/`
3. On startup: initializes SQLite DB, seeds salary data from `seed_data/nhl_players_2025_26.csv` if empty, serves both API and frontend on a single port

## Project Structure

```
├── server/                 # FastAPI backend
│   ├── main.py             # App entry, static files, CORS
│   ├── auth.py             # HMAC cookie auth
│   ├── constants.py        # Team mappings, defaults, season detection
│   ├── database.py         # SQLite setup
│   ├── seed.py             # Auto-seed salary CSV on first startup
│   ├── routes/
│   │   ├── optimizer.py    # /api/optimize, /api/settings, /api/players
│   │   └── salary.py       # /api/salary/upload, /api/salary/status
│   └── services/
│       ├── nhl_api.py      # NHL API fetch + cache
│       ├── injuries.py     # CBS Sports injury scraping
│       ├── salary.py       # CSV upload/parse
│       ├── projections.py  # Fantasy point projections + data assembly
│       └── optimizer.py    # PuLP ILP solver
├── src/                    # React frontend
│   ├── App.tsx             # Main app shell
│   ├── lib/
│   │   ├── api.ts          # Typed fetch wrapper
│   │   └── types.ts        # TypeScript interfaces
│   └── components/         # UI components
├── seed_data/              # Initial salary CSV
├── Dockerfile              # Multi-stage build
├── requirements.txt        # Python deps
└── vite.config.ts          # Vite + dev proxy config
```

## Updating Salary Data

The app ships with salary data from `seed_data/nhl_players_2025_26.csv` which is auto-loaded on first startup. To update mid-season:

1. Get a new CSV from PuckPedia (or run the Salary Cap notebook)
2. Upload via the UI (Salary Data section) — this does a full table replacement

## How the Optimizer Works

1. Fetches player stats from NHL API (32 teams, cached 12h)
2. Fetches standings + weekly schedule
3. Calculates schedule strength multipliers (weaker opponents = higher multiplier)
4. Projects fantasy points: `(goals/game * 2 + assists/game) * games_this_week * multiplier`
5. Scrapes injuries from CBS Sports, zeros injured players
6. Merges with salary data (exact name match + last-name fallback)
7. Adds team-level goalie projections (win probability model)
8. Runs PuLP ILP solver to maximize points subject to salary cap + roster constraints
