import streamlit as st
import requests
import pandas as pd
from operator import itemgetter

LEAGUE_ID = "696993"  # Replace with actual League ID

@st.cache_data
def get_events():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["events"], r.json()["elements"]

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
    data = r.json()
    return {
        "points": data["entry_history"]["points"],
        "overall_rank": data["entry_history"]["overall_rank"],
        "captain_id": next((p["element"] for p in data["picks"] if p.get("is_captain")), None)
    }

@st.cache_data
def get_entry_history(entry_id):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/history/"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["current"]


def get_top_performers(league_id, gw, players_dict):
    standings = get_league_standings(league_id)
    gw_data = []

    for player in standings:
        entry_id = player["entry"]
        team = player["entry_name"]
        manager = player["player_name"]
        group_rank = player.get("rank")
        try:
            data = get_manager_gw_score(entry_id, gw)
            gw_data.append({
                "Team": team,
                "Manager": manager,
                "GW Score": data["points"],
                "Overall Rank": data["overall_rank"],
                "Group Rank": group_rank,
                "Captain": players_dict.get(data["captain_id"], {}).get("web_name", "N/A")
            })
        except:
            continue

    df = pd.DataFrame(gw_data)
    df = df.sort_values(by="GW Score", ascending=False)

    # Preserve ties in top 3
    top_scores = df["GW Score"].unique()[:3]
    top_df = df[df["GW Score"].isin(top_scores)].reset_index(drop=True)

    return top_df, df


def get_most_improved(df, last_group_ranks):
    temp = df.copy()
    temp["Previous Group Rank"] = temp["Manager"].map(last_group_ranks)
    temp["Rank Change"] = temp["Previous Group Rank"] - temp["Group Rank"]
    return temp.sort_values(by="Rank Change", ascending=False).head(1)

# --- Streamlit UI ---
st.title("🏆 Fantasy Premier League Dashboard")

events, elements = get_events()
players_dict = {p["id"]: p for p in elements}

finished_gws = [e for e in events if e["finished"]]
gameweek_options = [e["id"] for e in finished_gws]
gameweek_names = [f"GW {e['id']}" for e in finished_gws]

selected_index = st.selectbox(
    "Select Gameweek",
    range(len(gameweek_options)),
    index=len(gameweek_options) - 1,
    format_func=lambda i: gameweek_names[i]
)
selected_gw = gameweek_options[selected_index]

if st.button("Go"):
    top_df, all_df = get_top_performers(LEAGUE_ID, selected_gw, players_dict)

    # 🏆 Highlight Winner
    if not top_df.empty:
        top_df.iloc[0, top_df.columns.get_loc("Team")] = "🏆 " + top_df.iloc[0]["Team"]

    st.subheader(f"Top Performers – Gameweek {selected_gw}")
    st.dataframe(top_df)

    # 🎯 Average Score
    avg_score = all_df["GW Score"].mean() if not all_df.empty else 0
    st.metric("League Average Score", f"{avg_score:.1f}")

    # 📈 Most Improved based on Group Rank
    if selected_gw > 1:
        _, last_df = get_top_performers(LEAGUE_ID, selected_gw - 1, players_dict)
        last_group_ranks = dict(zip(last_df["Manager"], last_df["Group Rank"]))
        most_improved = get_most_improved(all_df, last_group_ranks)
        st.subheader("📈 Most Improved (Group Rank)")
        st.table(most_improved[["Manager", "Team", "Rank Change"]])

    # 🧠 Most Common Captains
    st.subheader("🧠 Most Common Captains")
    if all_df["Captain"].dropna().any():
        top_captains = all_df["Captain"].value_counts().head(3)
        captain_df = top_captains.reset_index()
        captain_df.columns = ["Player", "Times Picked"]
        st.table(captain_df)
    else:
        st.warning("No captain data available.")
