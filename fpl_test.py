import requests
from operator import itemgetter

LEAGUE_ID = "696993"  # Replace with your actual league ID

def get_events():
    r = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    r.raise_for_status()
    return r.json()["events"]

def get_league_standings(league_id):
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["standings"]["results"]

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
            continue  # Manager may not have played that GW

    gw_scores.sort(key=itemgetter("GW Score"), reverse=True)

    top_scores = []
    unique_scores = set()
    for row in gw_scores:
        if len(unique_scores) >= 3 and row["GW Score"] not in unique_scores:
            break
        top_scores.append(row)
        unique_scores.add(row["GW Score"])

    return top_scores

# Run the logic
if __name__ == "__main__":
    events = get_events()
    finished_gws = [e["id"] for e in events if e["finished"]]
    latest_gw = max(finished_gws)

    print(f"\n🔢 Checking Gameweek {latest_gw}...\n")
    top = get_top_performers(LEAGUE_ID, latest_gw)

    if top:
        for i, row in enumerate(top, 1):
            print(f"{i}. {row['Manager']} ({row['Team']}) - {row['GW Score']} pts")
    else:
        print("No data found or league is empty.")
