import json
import os
from datetime import datetime

# Files
DATA_FILE = "characters.json"
MATCH_LOG_FILE = "match_log.json"

# Import your ELO components from app.py
from app import calculate_elo_custom, CHARACTERS, compute_global_elo


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


print("=== REBUILDING ELO FROM MATCH HISTORY ===")

# ------------------------
# 1. LOAD DATA & BACKUP
# ------------------------
players = {}
match_log = load_json(MATCH_LOG_FILE, [])

if not match_log:
    print("No match history found. Cannot rebuild.")
    exit(1)

# Backup old files
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
os.system(f"cp {DATA_FILE} characters_backup_{timestamp}.json")
os.system(f"cp {MATCH_LOG_FILE} match_log_backup_{timestamp}.json")

print("Backups created.")


# ------------------------
# 2. RESET ALL RATINGS
# ------------------------
players = {}  # fully empty
print("Ratings cleared. Beginning replay...")



# ----------------------------------------
# 3. SAFE CHRONOLOGICAL SORTING
# ----------------------------------------
fixed_matches = []
fallback_start = datetime(2000, 1, 1, 0, 0)

for index, m in enumerate(match_log):
    ts = m.get("timestamp", "")

    # Try to parse normally
    try:
        parsed = datetime.strptime(ts, "%Y-%m-%d %H:%M")
    except Exception:
        # Assign a synthetic timestamp so order is preserved
        parsed = fallback_start.replace(
            hour=(index // 60) % 24,
            minute=index % 60
        )
        m["timestamp"] = "N/A"

    m["_parsed_time"] = parsed
    fixed_matches.append(m)

match_log_sorted = sorted(fixed_matches, key=lambda m: m["_parsed_time"])



for i, match in enumerate(match_log_sorted, start=1):
    p1 = match["p1"]
    c1 = match["c1"]
    p2 = match["p2"]
    c2 = match["c2"]
    winner = match["winner"]

    # Initialize players & characters at 1000
    if p1 not in players:
        players[p1] = {}
    if p2 not in players:
        players[p2] = {}
    if c1 not in players[p1]:
        players[p1][c1] = 1000
    if c2 not in players[p2]:
        players[p2][c2] = 1000

    old1 = players[p1][c1]
    old2 = players[p2][c2]

    # Compute global ratings BEFORE this match
    p1_global = compute_global_elo(p1, players)
    p2_global = compute_global_elo(p2, players)

    # Recompute match ELO using your new system
    new1, new2 = calculate_elo_custom(
        old1, old2,
        p1_global, p2_global,
        winner
    )

    # Update ratings
    players[p1][c1] = new1
    players[p2][c2] = new2

    # Update diffs inside match log entry
    match["new1"] = new1
    match["new2"] = new2
    match["diff1"] = new1 - old1
    match["diff2"] = new2 - old2

    if i % 50 == 0:
        print(f"Processed {i}/{len(match_log_sorted)} matches...")



# ------------------------
# 4. SAVE NEW MATCH LOG + PLAYER RATINGS
# ------------------------

# Remove temporary timestamp field
for m in match_log_sorted:
    if "_parsed_time" in m:
        del m["_parsed_time"]

# Save new match log with updated ELO + diffs
save_json(MATCH_LOG_FILE, match_log_sorted)

# Save rebuilt player ratings
save_json(DATA_FILE, players)

print("\n=== REBUILD COMPLETE ===")
print(f"Total players: {len(players)}")
print(f"Total matches processed: {len(match_log_sorted)}")
print("New leaderboard is now active.")

