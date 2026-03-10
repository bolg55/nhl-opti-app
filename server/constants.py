from datetime import date

# Auto-detect season: if month >= September, use current year; else prior year
today = date.today()
SEASON_START_YEAR = today.year if today.month >= 9 else today.year - 1
SEASON_INT = f"{SEASON_START_YEAR}{SEASON_START_YEAR + 1}"

# Maps full team names (salary CSV) → NHL API 3-letter codes
FULL_NAME_TO_ABBREV = {
    "Anaheim Ducks": "ANA",
    "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY",
    "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI",
    "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ",
    "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET",
    "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA",
    "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN",
    "Montréal Canadiens": "MTL",
    "Montreal Canadiens": "MTL",
    "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD",
    "New York Islanders": "NYI",
    "New York Rangers": "NYR",
    "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL",
    "St Louis Blues": "STL",
    "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR",
    "Utah Hockey Club": "UTA",
    "Utah Mammoth": "UTA",
    "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK",
    "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}

# CBS Sports uses shortened team names
CBS_TEAM_TO_ABBREV = {
    "Anaheim": "ANA",
    "Arizona": "UTA",
    "Boston": "BOS",
    "Buffalo": "BUF",
    "Calgary": "CGY",
    "Carolina": "CAR",
    "Chicago": "CHI",
    "Colorado": "COL",
    "Columbus": "CBJ",
    "Dallas": "DAL",
    "Detroit": "DET",
    "Edmonton": "EDM",
    "Florida": "FLA",
    "Los Angeles": "LAK",
    "Minnesota": "MIN",
    "Montreal": "MTL",
    "Nashville": "NSH",
    "New Jersey": "NJD",
    "N.Y. Islanders": "NYI",
    "N.Y. Rangers": "NYR",
    "Ottawa": "OTT",
    "Philadelphia": "PHI",
    "Pittsburgh": "PIT",
    "San Jose": "SJS",
    "Seattle": "SEA",
    "St. Louis": "STL",
    "Tampa Bay": "TBL",
    "Toronto": "TOR",
    "Utah": "UTA",
    "Vancouver": "VAN",
    "Vegas": "VGK",
    "Washington": "WSH",
    "Winnipeg": "WPG",
}

# All 32 NHL API team codes
ALL_TEAMS = sorted(set(FULL_NAME_TO_ABBREV.values()))

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
