import streamlit as st
import requests
import pandas as pd

LEAGUE_ID = "696993"  # Replace with your actual League ID

# --- Fresh fetch function (no cache) ---
def fetch_events():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    return data["events"], data["elements"]

def get_events(fresh=False):
    if fresh:
        return fetch_events()
    return fetch_events()  # You can cache this later if needed

def get_league_standings(league_id):
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["standings"]["results"]

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

# --- Streamlit UI ---
st.title("🏆 FPL Mech Peeps Dashboard")

# --- Refresh mechanism ---
refresh = st.button("🔁 Refresh Gameweek List")
if refresh:
    st.session_state["refresh"] = True

if st.session_state.get("refresh", False):
    events, elements = get_events(fresh=True)
    st.session_state["refresh"] = False
else:
    events, elements = get_events()


# Option to include in-progress Gameweeks
show_unfinished = st.checkbox("Show in-progress Gameweeks", value=False)

if show_unfinished:
    available = [e for e in events if e["data_checked"]]
else:
    available = [e for e in events if e["finished"]]

gws = [e["id"] for e in available]
gw_labels = [e["name"] for e in available]

sel = st.selectbox("Select Gameweek", range(len(gws)), index=len(gws)-1, format_func=lambda i: gw_labels[i])
current_gw = gws[sel]

if st.button("Go"):
    top_df, all_df = get_top_performers(LEAGUE_ID, current_gw)

    # Highlight winners
    top_df.loc[top_df["Weekly Rank"] == 1, "Team"] = "🏆 " + top_df.loc[top_df["Weekly Rank"] == 1, "Team"]

    st.subheader(f"Top Performers – Gameweek {current_gw}")
    st.dataframe(top_df, hide_index=True)

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
    st.dataframe(cap_df, hide_index=True)
