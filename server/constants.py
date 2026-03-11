from datetime import date

# Auto-detect season: if month >= September, use current year; else prior year
today = date.today()
SEASON_START_YEAR = today.year if today.month >= 9 else today.year - 1
SEASON_INT = f"{SEASON_START_YEAR}{SEASON_START_YEAR + 1}"

# All 32 NHL API team codes
ALL_TEAMS = [
    "ANA", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI", "COL",
    "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL", "NJD",
    "NSH", "NYI", "NYR", "OTT", "PHI", "PIT", "SEA", "SJS",
    "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WPG", "WSH",
]

# Default optimizer constraints
DEFAULT_SETTINGS = {
    "max_cost": 70.5,
    "min_cost_pct": 90,
    "num_forwards": 6,
    "num_defensemen": 4,
    "num_goalies": 2,
    "max_per_team": 5,
    "min_games_played": 10,
}

# Cache TTL in hours
CACHE_HOURS = 12

# NHL API base URL
NHL_API_BASE = "https://api-web.nhle.com/v1"
