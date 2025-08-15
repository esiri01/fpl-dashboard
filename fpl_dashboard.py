import streamlit as st
import requests
import pandas as pd

LEAGUE_ID = "416802"  # Replace with actual League ID

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
    df = df.sort_values(by="GW Score", ascending=False)
    df["Weekly Rank"] = df["GW Score"].rank(method="dense", ascending=False).astype(int)

    top_scores = df["GW Score"].unique()[:3]
    top_df = df[df["GW Score"].isin(top_scores)].reset_index(drop=True)
    return top_df, df


def get_most_improved(current_df, previous_df):
    prev_ranks = previous_df.set_index("Manager")["Weekly Rank"].to_dict()
    temp = current_df.copy()
    temp["Previous Weekly Rank"] = temp["Manager"].map(prev_ranks)
    temp["Rank Change"] = temp["Previous Weekly Rank"] - temp["Weekly Rank"]
    return temp.sort_values(by="Rank Change", ascending=False).head(1)

# --- Streamlit UI ---
st.title("🏆 FPL Mech Peeps Dashboard")

events, elements = get_events()





available = [e for e in events if e["data_checked"] or e["finished"]]


# Always add the current Gameweek
current_gameweek = next((e for e in events if e["is_current"]), None)
if current_gameweek:
    available.append(current_gameweek)


# Prepare the list of Gameweek ids and labels
gws = [e["id"] for e in available]
gw_labels = [e["name"] for e in available]

# Select Gameweek
sel = st.selectbox("Select Gameweek", range(len(gws)), index=len(gws)-1, format_func=lambda i: gw_labels[i])
current_gw = gws[sel]

if st.button("Go"):
    # Fetch data
    top_df, all_df = get_top_performers(LEAGUE_ID, current_gw)

    # Highlight winners
    top_df.loc[top_df["Weekly Rank"] == 1, "Team"] = "🏆 " + top_df.loc[top_df["Weekly Rank"] == 1, "Team"]

    st.subheader(f"Top Performers – Gameweek {current_gw}")
    st.table(top_df.reset_index(drop=True))

    # League Average
    avg = all_df["GW Score"].mean() if not all_df.empty else 0
    st.metric("League Average Score", f"{avg:.1f}")

    # Most Common Captains
    st.subheader("🧠 Most Common Captains")
    standings = get_league_standings(LEAGUE_ID)
    cap_ids = []
    for p in standings:
        try:
            picks = requests.get(f"https://fantasy.premierleague.com/api/entry/{p['entry']}/event/{current_gw}/picks/").json()["picks"]
            cap = next(item for item in picks if item.get("is_captain"))["element"]
            cap_ids.append(cap)
        except:
            continue
    name_map = {el["id"]: el["web_name"] for el in elements}
    cap_names = [name_map.get(c, "N/A") for c in cap_ids]
    cap_series = pd.Series(cap_names).value_counts().head(3)
    cap_df = cap_series.reset_index()
    cap_df.columns = ["Player", "Times Picked"]
    st.table(cap_df.reset_index(drop=True))
