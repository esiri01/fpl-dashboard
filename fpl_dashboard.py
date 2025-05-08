import streamlit as st
import pandas as pd
import requests
import time
from collections import Counter

# ========== CONFIGURATION ==========
LEAGUE_ID = "696993" # Replace this with your actual FPL league ID

# ========== API FUNCTIONS ==========

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
    elements = data["elements"]
    players = {p["id"]: f'{p["first_name"]} {p["second_name"]}' for p in elements}
    return players

def get_top_performers(league_id, gw, players_dict):
    standings = get_league_standings(league_id)

    result = []
    captain_counter = Counter()

    for entry in standings:
        entry_id = entry["entry"]
        manager_name = entry["entry_name"]
        rank = entry["rank"]

        try:
            picks_url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/"
            picks = requests.get(picks_url).json()
            chip_used = picks.get("chip", "None")
            captain_id = next((p["element"] for p in picks["picks"] if p["is_captain"]), None)
            captain_name = players_dict.get(captain_id, "Unknown")
            captain_counter[captain_name] += 1

            entry_url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/"
            event_data = requests.get(entry_url).json()
            points = event_data.get("points", 0)

            result.append({
                "Manager": manager_name,
                "Points": points,
                "Rank": rank,
                "Chip Used": chip_used,
                "Captain": captain_name
            })

        except Exception as e:
            print(f"Error fetching data for {entry_id}: {e}")
            continue

        time.sleep(0.5)

    df = pd.DataFrame(result)
    df = df.sort_values("Points", ascending=False)
    top_score = df["Points"].nlargest(3).values
    cutoff = top_score[-1] if len(top_score) == 3 else top_score[-1]
    top_df = df[df["Points"] >= cutoff].reset_index(drop=True)

    # Top captains
    top_captains = pd.DataFrame(captain_counter.items(), columns=["Player", "Times Picked"])
    top_captains = top_captains.sort_values("Times Picked", ascending=False)

    return top_df, df.reset_index(drop=True), top_captains

# ========== STREAMLIT UI ==========

st.set_page_config(page_title="FPL Weekly Dashboard", layout="wide")

st.title("⚽ FPL Weekly Performance Dashboard")

players_dict = get_players_dict()

selected_gw = st.number_input("Select Gameweek", min_value=1, max_value=38, value=1)

if st.button("Go"):
    try:
        top_df, all_df, top_captains = get_top_performers(LEAGUE_ID, selected_gw, players_dict)

        st.subheader("🏆 Top Performers of the Week")
        st.table(top_df)

        st.subheader("📋 Full Standings")
        st.dataframe(all_df)

        st.subheader("🧢 Most Chosen Captains")
        st.table(top_captains)

    except requests.HTTPError as e:
        st.error(f"HTTP Error: {e}")
    except Exception as e:
        st.error(f"Something went wrong: {e}")
