from datetime import date

# Auto-detect season: if month >= September, use current year; else prior year
today = date.today()
SEASON_START_YEAR = today.year if today.month >= 9 else today.year - 1
SEASON_INT = f"{SEASON_START_YEAR}{SEASON_START_YEAR + 1}"
# Previous season, used as a fallback for stats before the new season has games played
PREVIOUS_SEASON_INT = f"{SEASON_START_YEAR - 1}{SEASON_START_YEAR}"
# Two seasons before that, used only for shooting %, so one off year doesn't define a finisher
OLDER_SHOOTING_SEASONS = [f"{y}{y + 1}" for y in (SEASON_START_YEAR - 2, SEASON_START_YEAR - 3)]

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

# Games of .500 hockey blended into every team's points %. Early-season records are
# mostly noise (a 1-4-1 start is .167); this keeps opponent strength and goalie win odds
# from swinging on a handful of games. Rough estimate: over 82 games, luck is about half
# the spread in points %, which works out to ~35 games. Higher = more conservative.
STANDINGS_PRIOR_GAMES = 35

# Shots of league-average shooting blended into every player's shooting %, which is
# mostly luck over small samples. Estimated from 2025-26: ~190 for forwards, ~180 for D.
SHOOTING_PRIOR_SHOTS = 180

# Cache TTL in hours
CACHE_HOURS = 12

# NHL API base URL
NHL_API_BASE = "https://api-web.nhle.com/v1"
