import streamlit as st
import requests
from operator import itemgetter

LEAGUE_ID = "696993"  # Replace with your real league ID

@st.cache_data
def get_events():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["events"]

@st.cache_data
def get_league_standings(league_id):
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["standings"]["results"]

@st.cache_data
def get_manager_gw_score(entry_id, gw):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["entry_history"]["points"]

def get_top_performers(league_id, gw):
    standings = get_league_standings(league_id)
    gw_scores = []

    for player in standings:
        entry_id = player["entry"]
        team = player["entry_name"]
        manager = player["player_name"]
        try:
            score = get_manager_gw_score(entry_id, gw)
            gw_scores.append({"Team": team, "Manager": manager, "GW Score": score})
        except:
            continue  # In case the player didn't play that GW

    gw_scores.sort(key=itemgetter("GW Score"), reverse=True)

    # Get top 3 unique scores, include ties
    top_scores = []
    unique_scores = set()
    for row in gw_scores:
        if len(unique_scores) >= 3 and row["GW Score"] not in unique_scores:
            break
        top_scores.append(row)
        unique_scores.add(row["GW Score"])

    return top_scores

# Streamlit UI
st.title("🏆 FPL Gameweek Top Performers")

events = get_events()
gameweek_options = [e["id"] for e in events if e["finished"]]
gameweek_names = [f"GW {e['id']}" for e in events if e["finished"]]
latest_gw = max(gameweek_options)

selected_index = st.selectbox("Select Gameweek", range(len(gameweek_options)), index=len(gameweek_options) - 1, format_func=lambda i: gameweek_names[i])
selected_gw = gameweek_options[selected_index]

top = get_top_performers(LEAGUE_ID, selected_gw)

if top:
    st.subheader(f"Top Performers - Gameweek {selected_gw}")
    st.table(top)
else:
    st.warning("No data available for this Gameweek yet.")
