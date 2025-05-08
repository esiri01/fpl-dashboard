import streamlit as st
import pandas as pd
import requests
import time
from collections import Counter

# ========== CONFIG ==========
LEAGUE_ID = "696993"  # Replace with your real FPL league ID

# ========== API HELPERS ==========

@st.cache_data(show_spinner=False)
def get_league_standings(league_id):
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["standings"]["results"]

@st.cache_data(show_spinner=False)
def get_players_dict():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    return {p["id"]: f'{p["first_name"]} {p["second_name"]}' for p in data["elements"]}

def get_top_performers(league_id, gw, players_dict):
    standings = get_league_standings(league_id)

    results = []
    captain_counter = Counter()

    for entry in standings:
        entry_id = entry["entry"]
        manager_name = entry["entry_name"]
        rank = entry["rank"]

        try:
            # Picks (for chip + captain)
            picks_url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/"
            picks = requests.get(picks_url).json()
            chip_used = picks.get("chip", "None")
            captain_id = next((p["element"] for p in picks["picks"] if p["is_captain"]), None)
            captain_name = players_dict.get(captain_id, "Unknown")
            captain_counter[captain_name] += 1

            # Event Summary (for points)
            event_url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/"
            event_data = requests.get(event_url).json()
            points = event_data.get("points", None)

            if points is None:
                continue

            results.append({
                "Manager": manager_name,
                "Points": points,
                "Rank": rank,
                "Chip Used": chip_used,
                "Captain": captain_name
            })

        except Exception as e:
            print(f"Error for entry {entry_id}: {e}")
            continue

        time.sleep(0.4)  # Rate limit

    if not results:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values("Points", ascending=False)

    # Handle top 3 with ties
    if len(df) <= 3:
        top_df = df
    else:
        top_scores = df["Points"].nlargest(3).values
        cutoff = top_scores[-1]
        top_df = df[df["Points"] >= cutoff]

    # Top captains
    top_captains = pd.DataFrame(captain_counter.items(), columns=["Player", "Times Picked"])
    top_captains = top_captains.sort_values("Times Picked", ascending=False)

    return top_df.reset_index(drop=True), df.reset_index(drop=True), top_captains

# ========== STREAMLIT UI ==========

st.set_page_config("FPL Weekly Dashboard", layout="wide")
st.title("⚽ FPL Weekly Performance Dashboard")

players_dict = get_players_dict()

selected_gw = st.selectbox("Select Gameweek", options=list(range(1, 39)), index=0)

if st.button("Go"):
    with st.spinner("Fetching data..."):
        top_df, all_df, top_captains = get_top_performers(LEAGUE_ID, selected_gw, players_dict)

    if top_df.empty:
        st.warning(f"No data available for Gameweek {selected_gw}. It may not have finished yet.")
    else:
        st.subheader("🏆 Top Performers of the Week")
        st.table(top_df)

        st.subheader("📋 Full League Standings for GW")
        st.dataframe(all_df)

        st.subheader("🧢 Most Chosen Captains")
        st.table(top_captains)
