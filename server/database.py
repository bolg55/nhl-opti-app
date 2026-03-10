import os
import sqlite3
import threading

DB_DIR = os.environ.get("DATA_DIR", "data")
DB_PATH = os.path.join(DB_DIR, "nhl-optimizer.db")

_write_lock = threading.Lock()


def get_db() -> sqlite3.Connection:
    """Get SQLite connection with tables created."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_write_lock() -> threading.Lock:
    return _write_lock


def init_db():
    """Create tables and seed defaults on startup."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS cache_metadata (
        table_name TEXT PRIMARY KEY,
        updated_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS player_stats (
        player_name TEXT,
        team TEXT,
        position TEXT,
        games_played INTEGER,
        goals INTEGER,
        assists INTEGER,
        shots INTEGER,
        avg_toi_seconds REAL,
        goals_per_game REAL,
        assists_per_game REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS standings (
        team TEXT PRIMARY KEY,
        team_name TEXT,
        point_pctg REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS salary_data (
        player TEXT,
        team TEXT,
        position TEXT,
        cap_hit TEXT,
        pv REAL,
        player_key TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS optimizer_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        max_cost REAL,
        min_cost_pct REAL,
        num_forwards INTEGER,
        num_defensemen INTEGER,
        num_goalies INTEGER,
        max_per_team INTEGER,
        min_games_played INTEGER
    )""")
    conn.commit()

    # Seed default settings if not present
    row = conn.execute("SELECT id FROM optimizer_settings WHERE id = 1").fetchone()
    if row is None:
        from server.constants import DEFAULT_SETTINGS

        conn.execute(
            """INSERT INTO optimizer_settings
            (id, max_cost, min_cost_pct, num_forwards, num_defensemen, num_goalies, max_per_team, min_games_played)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)""",
            (
                DEFAULT_SETTINGS["max_cost"],
                DEFAULT_SETTINGS["min_cost_pct"],
                DEFAULT_SETTINGS["num_forwards"],
                DEFAULT_SETTINGS["num_defensemen"],
                DEFAULT_SETTINGS["num_goalies"],
                DEFAULT_SETTINGS["max_per_team"],
                DEFAULT_SETTINGS["min_games_played"],
            ),
        )
        conn.commit()
    conn.close()
