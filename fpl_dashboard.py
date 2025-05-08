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
        "rank": data["entry_history"]["overall_rank"],
        "captain_id": next(p["element"] for p in data["picks"] if p["is_captain"])
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
        try:
            data = get_manager_gw_score(entry_id, gw)
            gw_data.append({
                "Team": team,
                "Manager": manager,
                "GW Score": data["points"],
                "Overall Rank": data["rank"],
                "Captain": players_dict[data["captain_id"]]["web_name"]
            })
        except:
            continue

    df = pd.DataFrame(gw_data)
    df = df.sort_values(by="GW Score", ascending=False)

    # Preserve ties in top 3
    top_scores = df["GW Score"].unique()[:3]
    top_df = df[df["GW Score"].isin(top_scores)].reset_index(drop=True)

    return top_df, df

def get_most_improved(df, last_gw_ranks):
    df = df.copy()
    df["Previous Rank"] = df["Manager"].map(last_gw_ranks)
    df["Rank Change"] = df["Previous Rank"] - df["Overall Rank"]
    return df.sort_values(by="Rank Change", ascending=False).head(1)

def get_rank_history(league_id):
    standings = get_league_standings(league_id)
    rank_history = {}

    for player in standings:
        manager = player["player_name"]
        entry_id = player["entry"]
        history = get_entry_history(entry_id)
        gw_scores = [h["points"] for h in history]
        rank_history[manager] = gw_scores

    return pd.DataFrame(rank_history)

# --- Streamlit UI ---
st.title("🏆 Fantasy Premier League Dashboard")

events, elements = get_events()
players_dict = {p["id"]: p for p in elements}

finished_gws = [e for e in events if e["finished"]]
gameweek_options = [e["id"] for e in finished_gws]
gameweek_names = [f"GW {e['id']}" for e in finished_gws]
latest_gw = max(gameweek_options)

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
    top_df.iloc[0, top_df.columns.get_loc("Team")] = "🏆 " + top_df.iloc[0]["Team"]

    st.subheader(f"Top Performers – Gameweek {selected_gw}")
    st.dataframe(top_df)

    st.download_button("📥 Download Top Performers", top_df.to_csv(index=False), "top_performers.csv", "text/csv")

    # 🎯 Average Score
    avg_score = all_df["GW Score"].mean()
    st.metric("League Average Score", f"{avg_score:.1f}")

    # 📈 Most Improved
    if selected_gw > 1:
        last_gw_data = get_top_performers(LEAGUE_ID, selected_gw - 1, players_dict)[1]
        last_gw_ranks = dict(zip(last_gw_data["Manager"], last_gw_data["Overall Rank"]))
        most_improved = get_most_improved(all_df, last_gw_ranks)
        st.subheader("📈 Most Improved")
        st.table(most_improved[["Manager", "Team", "Rank Change"]])

    # 🧠 Most Common Captains
    st.subheader("🧠 Most Common Captains")
    if all_df["Captain"].notna().any():
        # Get most common captains
        top_captains = all_df["Captain"].value_counts().head(3)

        # Create a DataFrame for better visualization
        captain_df = top_captains.reset_index(names=["Player", "Times Picked"])

        # Display it as a table
        st.table(captain_df)
    else:
        st.warning("No captain data available.")


    # 📊 Score Trends
    st.subheader("📊 Score Trends of Top Managers")
    rank_history_df = get_rank_history(LEAGUE_ID)
    top_names = top_df["Manager"].tolist()
    filtered = rank_history_df[top_names]
    st.line_chart(filtered)