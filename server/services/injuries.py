import re
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

from server.constants import CBS_TEAM_TO_ABBREV


def clean_player_name(name: str) -> str:
    match = re.search(r"[a-z]([A-Z])", name)
    if match:
        return name[match.start() + 1 :].strip()
    return name.strip()


def get_current_injuries() -> pd.DataFrame:
    try:
        url = "https://www.cbssports.com/nhl/injuries/"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        injury_dataframes = []

        for wrapper in soup.find_all("div", class_="TableBaseWrapper"):
            team_name_tag = wrapper.find("span", class_="TeamName")
            if team_name_tag:
                team_name = team_name_tag.get_text(strip=True)
                table = wrapper.find("table", class_="TableBase-table")
                if table:
                    df = pd.read_html(StringIO(str(table)))[0]
                    df["Team"] = CBS_TEAM_TO_ABBREV.get(team_name, team_name)
                    injury_dataframes.append(df)

        if not injury_dataframes:
            return pd.DataFrame(columns=["Player", "Team"])

        injuries_df = pd.concat(injury_dataframes, ignore_index=True)
        injuries_df["Player"] = injuries_df["Player"].apply(clean_player_name)
        return injuries_df

    except Exception:
        return pd.DataFrame(columns=["Player", "Team"])
