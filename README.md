# NHL Fantasy Optimizer

Weekly salary-cap fantasy hockey lineup optimizer. FastAPI + React web app with PuLP integer linear programming solver.
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

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PASSWORD` | `dev` | Login password |
| `SECRET_KEY` | `dev-secret-key-change-in-production` | HMAC signing key for session cookies |
| `ENVIRONMENT` | `development` | Set to `production` for secure cookies |
| `DATA_DIR` | `data` | Directory for settings JSON file |
| `NHL_SALARY_API_URL` | `https://nhl-salary-api-production.up.railway.app` | Salary API base URL |
| `NHL_SALARY_API_TOKEN` | _(empty)_ | Bearer token for salary API (required in production) |

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
   - `NHL_SALARY_API_URL` — salary API base URL
   - `NHL_SALARY_API_TOKEN` — Bearer token for salary API auth
5. Add a persistent volume mounted at `/app/data` (for settings persistence across deploys)
6. Deploy

Railway provides the `PORT` env var automatically. The health check endpoint is `GET /api/health`.

### What the Docker build does

1. **Stage 1 (Node):** Installs frontend deps, runs `pnpm build` to produce `dist/`
2. **Stage 2 (Python):** Installs backend deps, copies `server/` and built `dist/`
3. On startup: ensures data directory exists, serves both API and frontend on a single port

## Project Structure

```
├── server/                 # FastAPI backend
│   ├── main.py             # App entry, static files, CORS
│   ├── auth.py             # HMAC cookie auth
│   ├── cache.py            # In-memory TTL cache
│   ├── constants.py        # Team codes, defaults, season detection
│   ├── routes/
│   │   ├── optimizer.py    # /api/optimize, /api/settings, /api/players
│   │   └── admin.py        # /api/admin/scrape-players, /api/admin/scrape-injuries
│   └── services/
│       ├── nhl_api.py      # NHL API fetch + cache
│       ├── salary_api.py   # Salary/injury API client
│       ├── projections.py  # Fantasy point projections + data assembly
│       └── optimizer.py    # PuLP ILP solver
├── src/                    # React frontend
│   ├── App.tsx             # Main app shell
│   ├── lib/
│   │   ├── api.ts          # Typed fetch wrapper
│   │   └── types.ts        # TypeScript interfaces
│   └── components/         # UI components
├── tests/                  # Python tests
├── Dockerfile              # Multi-stage build
├── requirements.txt        # Python deps
└── vite.config.ts          # Vite + dev proxy config
```

## Data Sources

- **[NHL API](https://api-web.nhle.com)** — Player stats, standings, weekly schedule (cached 12h)
- **[NHL Salary API](https://nhl-salary-api-production.up.railway.app)** — Player salaries and injury status (cached 30min)

Player data is joined on NHL player IDs for reliable matching.

## How the Optimizer Works

1. Fetches player stats from NHL API (32 teams, cached 12h)
2. Fetches standings + weekly schedule
3. Calculates schedule strength multipliers (weaker opponents = higher multiplier)
4. Projects fantasy points: `(goals/game * 2 + assists/game) * games_this_week * multiplier`
5. Fetches salary and injury data from the salary API
6. Joins stats with salary on player ID, zeros injured players
7. Adds team-level goalie projections (win probability model)
8. Runs PuLP ILP solver to maximize points subject to salary cap + roster constraints
