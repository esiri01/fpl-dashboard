import streamlit as st
import requests
import pandas as pd
from datetime import datetime

LEAGUE_ID = "416802"  # Replace with your League ID

# ---------- Data Access ----------
@st.cache_data
def get_events_and_elements():
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    return data["events"], data["elements"]

@st.cache_data
def get_league_standings(league_id: str):
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["standings"]["results"]

@st.cache_data
def get_manager_gw_score(entry_id: int, gw: int):
    url = f"https://fantasy.premierleague.com/api/entry/{entry_id}/event/{gw}/picks/"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    return data["entry_history"]["points"]

def get_top_performers(league_id: str, gw: int):
    standings = get_league_standings(league_id)
    data = []
    for p in standings:
        entry_id = p["entry"]
        try:
            score = get_manager_gw_score(entry_id, gw)
        except Exception:
            continue
        data.append(
            {
                "Team": p.get("entry_name"),
                "Manager": p.get("player_name"),
                "GW Score": score,
            }
        )
    df = pd.DataFrame(data)
    if df.empty:
        return df, df
    df = df.sort_values(by="GW Score", ascending=False)
    df["Weekly Rank"] = df["GW Score"].rank(method="dense", ascending=False).astype(int)

    top_scores = df["GW Score"].unique()[:3]
    top_df = df[df["GW Score"].isin(top_scores)].reset_index(drop=True)
    return top_df, df

def get_most_improved(current_df: pd.DataFrame, previous_df: pd.DataFrame):
    if current_df.empty or previous_df.empty:
        return pd.DataFrame()
    prev_ranks = previous_df.set_index("Manager")["Weekly Rank"].to_dict()
    temp = current_df.copy()
    temp["Previous Weekly Rank"] = temp["Manager"].map(prev_ranks)
    temp["Rank Change"] = temp["Previous Weekly Rank"] - temp["Weekly Rank"]
    return temp.sort_values(by="Rank Change", ascending=False).head(1)

# ---------- UI ----------
st.title("🏆 FPL Mech Peeps Dashboard")

events, elements = get_events_and_elements()

# Build available GWs: finished/checked/current OR already started (deadline has passed)
now = pd.Timestamp.now(tz='UTC')
available = [
    e for e in events
    if e.get("is_current") or e.get("data_checked") or e.get("finished")
    or (e.get("deadline_time") and pd.to_datetime(e["deadline_time"], utc=True) <= now)
]

# De-duplicate & sort by id
by_id = {e["id"]: e for e in available}
available = [by_id[k] for k in sorted(by_id.keys())]

labels_to_id = {e["name"]: e["id"] for e in available}
labels = list(labels_to_id.keys())

if not labels:
    st.warning("No available Gameweeks detected.")
    st.stop()

selected_label = st.selectbox("Select Gameweek", labels, index=len(labels) - 1)
current_gw = labels_to_id[selected_label]

# Find selected GW event info for status
selected_event = next((e for e in events if e["id"] == current_gw), None)
if selected_event:
    deadline = pd.to_datetime(selected_event["deadline_time"], utc=True)
    finished = selected_event.get("finished", False)
    now = pd.Timestamp.now(tz='UTC')
    # Only show "ongoing" or "completed"
    if finished:
        st.info(f"✅ {selected_label} is completed.")
    elif deadline <= now:
        st.info(f"🟢 {selected_label} is ongoing.")
    # If deadline in future and not finished, you may omit status or show not started if you prefer

if st.button("Go"):
    # Top performers
    top_df, all_df = get_top_performers(LEAGUE_ID, current_gw)

    st.subheader(f"Top Performers – {selected_label} (GW {current_gw})")
    if top_df.empty:
        st.warning("No data available for this Gameweek yet.")
        st.stop()

    # Highlight winners
    winners_mask = top_df["Weekly Rank"] == 1
    top_df.loc[winners_mask, "Team"] = "🏆 " + top_df.loc[winners_mask, "Team"]

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
            picks_resp = requests.get(
                f"https://fantasy.premierleague.com/api/entry/{p['entry']}/event/{current_gw}/picks/"
            )
            picks_resp.raise_for_status()
            picks = picks_resp.json().get("picks", [])
            cap = next((item for item in picks if item.get("is_captain")), None)
            if cap:
                cap_ids.append(cap["element"])
        except Exception:
            continue

    # Map player id -> web_name
    name_map = {el["id"]: el["web_name"] for el in elements}
    cap_names = [name_map.get(c, "N/A") for c in cap_ids]
    if cap_names:
        cap_series = pd.Series(cap_names).value_counts().head(3)
        cap_df = cap_series.reset_index()
        cap_df.columns = ["Player", "Times Picked"]
        st.table(cap_df.reset_index(drop=True))
    else:
        st.write("No captain data available for this Gameweek.")
