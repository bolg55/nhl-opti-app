from datetime import datetime
from io import StringIO

import pandas as pd

from server.constants import FULL_NAME_TO_ABBREV
from server.database import get_db, get_write_lock

REQUIRED_COLUMNS = {"Player", "Team", "Position", "pv"}


def upload_salary_csv(csv_content: str) -> int:
    df = pd.read_csv(StringIO(csv_content))

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")

    df["Team"] = df["Team"].map(FULL_NAME_TO_ABBREV)
    df["Position"] = df["Position"].map(
        lambda p: "G" if p == "G" else ("D" if p == "D" else "F")
    )
    df["player_key"] = df["Player"].str.strip().str.upper()

    cap_hit_col = "Cap Hit" in df.columns

    with get_write_lock():
        conn = get_db()
        try:
            conn.execute("DELETE FROM salary_data")
            for _, row in df.iterrows():
                conn.execute(
                    "INSERT INTO salary_data (player, team, position, cap_hit, pv, player_key) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        row["Player"],
                        row["Team"],
                        row["Position"],
                        row["Cap Hit"] if cap_hit_col else "",
                        float(row["pv"]),
                        row["player_key"],
                    ),
                )
            conn.execute(
                "INSERT OR REPLACE INTO cache_metadata (table_name, updated_at) VALUES (?, ?)",
                ("salary_data", datetime.now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    return len(df)


def get_salary_data() -> pd.DataFrame:
    conn = get_db()
    try:
        return pd.read_sql("SELECT * FROM salary_data", conn)
    finally:
        conn.close()


def get_salary_status() -> dict:
    conn = get_db()
    try:
        count = conn.execute("SELECT COUNT(*) FROM salary_data").fetchone()[0]
        row = conn.execute(
            "SELECT updated_at FROM cache_metadata WHERE table_name = 'salary_data'"
        ).fetchone()
        return {
            "count": count,
            "lastUpdated": row[0] if row else None,
        }
    finally:
        conn.close()
