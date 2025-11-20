import json
import os
from datetime import datetime
from app import calculate_elo  # uses your real elo function

MATCH_LOG_FILE = "match_log.json"

def load_match_log():
    if not os.path.exists(MATCH_LOG_FILE):
        return []
    with open(MATCH_LOG_FILE, "r") as f:
        return json.load(f)

def save_match_log(log):
    with open(MATCH_LOG_FILE, "w") as f:
        json.dump(log, f, indent=4)

def rebuild():
    log = load_match_log()
    if not log:
        print("No match log found.")
        return

    print(f"Loaded {len(log)} matches — rebuilding ELO history...")

    # Simulated ELO environment
    ratings = {}  # { player: { character: elo } }

    for m in log:
        p1 = m["p1"]
        c1 = m["c1"]
        p2 = m["p2"]
        c2 = m["c2"]
        winner = m["winner"]

        # Initialize missing ratings
        ratings.setdefault(p1, {})
        ratings.setdefault(p2, {})
        ratings[p1].setdefault(c1, 1000)
        ratings[p2].setdefault(c2, 1000)

        old1 = ratings[p1][c1]
        old2 = ratings[p2][c2]

        new1, new2 = calculate_elo(old1, old2, winner)

        ratings[p1][c1] = new1
        ratings[p2][c2] = new2

        # Store reconstructed values
        m["new1"] = new1
        m["new2"] = new2
        m["diff1"] = new1 - old1
        m["diff2"] = new2 - old2

        # Add fake timestamps if missing (ordered oldest → newest)
        if "timestamp" not in m:
            m["timestamp"] = "Rebuilt " + datetime.now().strftime("%Y-%m-%d %H:%M")

    save_match_log(log)
    print("Rebuild complete! match_log.json now contains full ELO history.")

if __name__ == "__main__":
    rebuild()
