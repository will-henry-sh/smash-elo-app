from flask import Flask, render_template, request, redirect, url_for
import json
import os
import subprocess
import threading

app = Flask(__name__)

def push_to_github():
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Auto-update from match submission"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("Git push successful.")
    except subprocess.CalledProcessError as e:
        print("Git push failed:", e)

# Detect Render environment
if os.getenv("RENDER"):
    DATA_DIR = "/var/data"  # Render persistent disk
else:
    DATA_DIR = "."  # Local folder for development

# Ensure the directory exists
os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = f"{DATA_DIR}/characters.json"
LAST_RESULT_FILE = f"{DATA_DIR}/last_result.json"
MATCH_LOG_FILE = f"{DATA_DIR}/match_log.json"


# run with alias "runelo" in terminal

# -----------------------------
# Data loading / saving helpers
# -----------------------------

def load_players():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_players(players):
    with open(DATA_FILE, "w") as f:
        json.dump(players, f, indent=4)

def save_last_result(result):
    with open(LAST_RESULT_FILE, "w") as f:
        json.dump(result, f, indent=4)

def load_last_result():
    if not os.path.exists(LAST_RESULT_FILE):
        return {}
    with open(LAST_RESULT_FILE, "r") as f:
        return json.load(f)

def load_match_log():
    if not os.path.exists(MATCH_LOG_FILE):
        return []
    with open(MATCH_LOG_FILE, "r") as f:
        return json.load(f)

def save_match_log(log):
    with open(MATCH_LOG_FILE, "w") as f:
        json.dump(log, f, indent=4)


# -----------------------------
# Character list
# -----------------------------

CHARACTERS = sorted([
    "Banjo & Kazooie", "Bayonetta", "Bowser", "Bowser Jr.",
    "Byleth", "Captain Falcon", "Charizard", "Chrom",
    "Cloud", "Corrin", "Daisy", "Dark Pit", "Dark Samus",
    "Diddy Kong", "Donkey Kong", "Dr. Mario", "Duck Hunt",
    "Falco", "Fox", "Ganondorf", "Greninja", "Hero",
    "Ice Climbers", "Ike", "Incineroar", "Inkling",
    "Isabelle", "Ivysaur", "Jigglypuff", "Joker",
    "Kazuya", "Ken", "King Dedede", "King K. Rool",
    "Kirby", "Link", "Little Mac", "Lucario", "Lucas",
    "Lucina", "Luigi", "Mario", "Marth", "Mega Man",
    "Meta Knight", "Mewtwo", "Mii Brawler",
    "Mii Gunner", "Mii Swordfighter", "Min Min",
    "Mr. Game and Watch", "Ness", "Olimar", "Pac-Man",
    "Palutena", "Peach", "Pichu", "Pikachu", "Piranha Plant",
    "Pit", "Pyra/Mythra", "R.O.B", "Richter", "Ridley",
    "Robin", "Rosalina and Luma", "Roy", "Ryu",
    "Samus", "Sephiroth", "Sheik", "Shulk", "Simon",
    "Snake", "Sonic", "Sora", "Squirtle", "Steve",
    "Terry", "Toon Link", "Villager", "Wario",
    "Wii Fit Trainer", "Wolf", "Yoshi", "Young Link",
    "Zelda", "Zero Suit Samus"
])


# -----------------------------
# ELO Calculation
# -----------------------------

def calculate_elo(p1_rating, p2_rating, winner, k=32):
    # Expected scores
    expected_p1 = 1 / (1 + 10 ** ((p2_rating - p1_rating) / 400))
    expected_p2 = 1 - expected_p1

    # Actual scores
    if winner == "p1":
        score_p1, score_p2 = 1, 0
    else:
        score_p1, score_p2 = 0, 1

    # New ratings
    new_p1 = p1_rating + k * (score_p1 - expected_p1)
    new_p2 = p2_rating + k * (score_p2 - expected_p2)

    # Apply floor of 800
    new_p1 = max(800, round(new_p1))
    new_p2 = max(800, round(new_p2))

    return new_p1, new_p2



# -----------------------------
# Routes
# -----------------------------

@app.route("/")
def index():
    data = load_players()
    last = load_last_result()
    
    player_list = sorted(list(data.keys()))

    return render_template(
        "index.html",
        players=data,
        characters=CHARACTERS,
        last=last,                          # <-- REQUIRED FOR RECENT MATCH BOX
        last_player1=last.get("last_player1", ""),
        last_player2=last.get("last_player2", ""),
        last_char1=last.get("last_char1", ""),
        last_char2=last.get("last_char2", ""),
        player_list=player_list
    )




@app.route("/leaderboard")
def leaderboard():
    data = load_players()
    rows = []

    for player, char_map in data.items():

        # Sum only the differences from 1000 for characters that have changed
        diffs = [(elo - 1000) for elo in char_map.values() if elo != 1000]

        global_elo = sum(diffs) if diffs else 0

        rows.append((player, global_elo, char_map))

    # Sort by global rating descending
    rows.sort(key=lambda x: x[1], reverse=True)

    return render_template("leaderboard.html", rows=rows)




@app.route("/player/<name>")
def player_stats(name):
    data = load_players()
    match_log = load_match_log()

    if name not in data:
        return f"Player '{name}' not found.", 404

    char_map = data[name]
    total_chars = len(char_map)

    # Best/Worst
    if char_map:
        best_char = max(char_map, key=lambda c: char_map[c])
        worst_char = min(char_map, key=lambda c: char_map[c])
    else:
        best_char = None
        worst_char = None

    # Stats
    total_matches = 0
    wins = 0
    losses = 0

    for m in match_log:
        if m["p1"] == name or m["p2"] == name:
            total_matches += 1

            if m["winner"] == "p1" and m["p1"] == name:
                wins += 1
            elif m["winner"] == "p2" and m["p2"] == name:
                wins += 1
            else:
                losses += 1

    win_rate = round((wins / total_matches) * 100, 1) if total_matches > 0 else 0

    return render_template(
        "player_stats.html",
        name=name,
        char_map=char_map,
        total_chars=total_chars,
        best_char=best_char,
        worst_char=worst_char,
        total_matches=total_matches,
        wins=wins,
        losses=losses,
        win_rate=win_rate
    )


@app.route("/reset", methods=["POST"])
def reset():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    if os.path.exists(MATCH_LOG_FILE):
        os.remove(MATCH_LOG_FILE)
    if os.path.exists(LAST_RESULT_FILE):
        os.remove(LAST_RESULT_FILE)
    return redirect(url_for("index"))


@app.route("/add_match", methods=["POST"])
def add_match():
    p1 = request.form["player1"]
    c1 = request.form["p1_character"]
    p2 = request.form["player2"]
    c2 = request.form["p2_character"]
    winner = request.form["winner"]

    data = load_players()

    # Initialize character ratings
    if p1 not in data:
        data[p1] = {}
    if c1 not in data[p1]:
        data[p1][c1] = 1000

    if p2 not in data:
        data[p2] = {}
    if c2 not in data[p2]:
        data[p2][c2] = 1000

    old1 = data[p1][c1]
    old2 = data[p2][c2]

    new1, new2 = calculate_elo(old1, old2, winner)

    data[p1][c1] = new1
    data[p2][c2] = new2

    save_players(data)

    # Save last match result
    save_last_result({
        "p1": p1,
        "c1": c1,
        "new1": new1,
        "diff1": new1 - old1,
        "p2": p2,
        "c2": c2,
        "new2": new2,
        "diff2": new2 - old2,
        "last_player1": p1,
        "last_player2": p2,
        "last_char1": c1,
        "last_char2": c2
    })

    # Log match history
    log = load_match_log()
    log.append({
        "p1": p1,
        "c1": c1,
        "p2": p2,
        "c2": c2,
        "winner": winner
    })
    save_match_log(log)

    # 🔥 Auto commit + push to GitHub (runs in background)
    threading.Thread(target=push_to_github).start()

    return redirect(url_for("index"))



if __name__ == "__main__":
    app.run(debug=True, port=5001)
