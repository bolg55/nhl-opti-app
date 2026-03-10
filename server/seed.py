import os

from server.database import get_db
from server.services.salary import upload_salary_csv


def seed_salary_data():
    """Auto-seed salary data from seed CSV if table is empty."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM salary_data").fetchone()[0]
    conn.close()

    if count > 0:
        return

    seed_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "seed_data",
        "nhl_players_2025_26.csv",
    )
    if not os.path.exists(seed_path):
        return

    with open(seed_path) as f:
        csv_content = f.read()

    n = upload_salary_csv(csv_content)
    print(f"Seeded {n} players from {seed_path}")
