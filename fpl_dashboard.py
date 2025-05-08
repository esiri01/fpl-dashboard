import streamlit as st
import requests
import pandas as pd

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
    return data["entry_history"]["points"]


def get_top_performers(league_id, gw):
    # Fetch standings and compute weekly scores
    standings = get_league_standings(league_id)
    data = []
    for p in standings:
        entry_id = p["entry"]
        try:
            score = get_manager_gw_score(entry_id, gw)
        except:
            continue
        data.append({
            "Team": p["entry_name"],
            "Manager": p["player_name"],
            "GW Score": score
        })
    df = pd.DataFrame(data)
    # Sort and compute weekly rank with ties
    df = df.sort_values(by="GW Score", ascending=False)
    df["Weekly Rank"] = df["GW Score"].rank(method="dense", ascending=False).astype(int)

    # Determine top scores (first three unique scores)
    top_scores = df["GW Score"].unique()[:3]
    top_df = df[df["GW Score"].isin(top_scores)].reset_index(drop=True)
    return top_df, df


def get_most_improved(current_df, previous_df):
    # Map previous weekly ranks
    prev_ranks = previous_df.set_index("Manager")["Weekly Rank"].to_dict()
    temp = current_df.copy()
    temp["Previous Weekly Rank"] = temp["Manager"].map(prev_ranks)
    temp["Rank Change"] = temp["Previous Weekly Rank"] - temp["Weekly Rank"]
    return temp.sort_values(by="Rank Change", ascending=False).head(1)

# --- Streamlit UI ---
st.title("🏆 Fantasy Premier League Dashboard")

events, elements = get_events()
finished = [e for e in events if e["finished"]]
gws = [e["id"] for e in finished]
gw_labels = [f"GW {id}" for id in gws]

sel = st.selectbox("Select Gameweek", range(len(gws)), index=len(gws)-1, format_func=lambda i: gw_labels[i])
current_gw = gws[sel]

if st.button("Go"):
    top_df, all_df = get_top_performers(LEAGUE_ID, current_gw)

    # Highlight all winners (rank 1)
    top_df.loc[top_df["Weekly Rank"] == 1, "Team"] = "🏆 " + top_df.loc[top_df["Weekly Rank"] == 1, "Team"]

    st.subheader(f"Top Performers – Gameweek {current_gw}")
    # Hide default index
    st.table(top_df.style.hide_index())

    # League Average
    avg = all_df["GW Score"].mean()
    st.metric("League Average Score", f"{avg:.1f}")

    # Most Improved based on Weekly Rank
    if current_gw > min(gws):
        _, prev_df = get_top_performers(LEAGUE_ID, current_gw-1)
        # Ensure both have Weekly Rank
        improved = get_most_improved(all_df, prev_df)
        st.subheader("📈 Most Improved (Weekly Rank)")
        st.table(improved[["Manager","Team","Rank Change"]].style.hide_index())

    # Captain picks
    st.subheader("🧠 Most Common Captains")
    # fetch picks for all
    caps = []
    for p in standings:
        entry_id = p["entry"]
        try:
            picks = requests.get(f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{current_gw}/picks/").json()["picks"]
            cap = next(item for item in picks if item.get("is_captain"))["element"]
            caps.append(cap)
        except:
            continue
    # map id to name
    names = {el["id"]: el["web_name"] for el in elements}
    cap_names = [names.get(c) for c in caps]
    cap_series = pd.Series(cap_names).value_counts().head(3)
    cap_df = cap_series.reset_index()
    cap_df.columns = ["Player","Times Picked"]
    st.table(cap_df.style.hide_index())
