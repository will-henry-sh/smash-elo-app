from flask import Flask, render_template, request, redirect, url_for
import json
import os
import subprocess
import threading
from functools import wraps
from datetime import datetime
from flask import Response

print("RUNNING FROM:", os.getcwd())
print("APP FILE:", __file__)
print(">>> LOADED FLASK APP FROM:", __file__)



app = Flask(__name__)

push_queue = []
is_pushing = False
push_log = []  # Stores recent push messages
MAX_LOGS = 20
# Admin login credentials
ADMIN_USERS = {
    "bunnyslave": "Letskill666",
    "todaycowboy": "Heisrisen!"
}
ADMIN_USERNAMES = ["Will", "Colton"]  # or ["Will", "YourOtherAdmins"]


def push_to_github_worker():
    global is_pushing

    if is_pushing:
        return

    is_pushing = True

    while push_queue:
        commit_message = push_queue.pop(0)

        try:
            subprocess.run(["git", "add", "-u"], check=True)

            diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"])
            if diff_check.returncode == 0:
                msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No changes to commit ({commit_message})"
                print(msg)
                push_log.append(msg)
                if len(push_log) > MAX_LOGS:
                    push_log.pop(0)
                continue

            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)

            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Git push successful: {commit_message}"
            print(msg)
            push_log.append(msg)
            if len(push_log) > MAX_LOGS:
                push_log.pop(0)

        except subprocess.CalledProcessError as e:
            msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Git push FAILED: {e}"
            print(msg)
            push_log.append(msg)
            if len(push_log) > MAX_LOGS:
                push_log.pop(0)

    is_pushing = False





def queue_push(commit_message="Auto-update from match submission"):
    """Adds a push request to the queue and starts worker if one isn't running."""
    push_queue.append(commit_message)
    threading.Thread(target=push_to_github_worker).start()


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

def check_auth(username, password):
    return ADMIN_USERS.get(username) == password

def authenticate():
    return Response(
        "Authentication required", 401,
        {"WWW-Authenticate": 'Basic realm="Admin Panel"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated



# -----------------------------
# Routes
# -----------------------------
@app.route('/badges')
def badges():
    badges = [
        {"badge": "Bloodlust", "description": "Win (3/5/10/25) matches in a row."},
        {"badge": "Defeatism", "description": "Lose 10 matches in a row."},
        {"badge": "Game Set", "description": "Win (10/50/100/500) total matches) "},
        {"badge": "Dominator", "description": "Three-stock another player."},
        {"badge": "Devastator", "description": "Three-stock another player three times in a row in a set."},
        {"badge": "Global Enthusiasm", "description": "Get ranked with every character."},
        {"badge": "Sky Full of Stars", "description": "Reach (1,000/2,000/3,000) global ELO ranking."},
        {"badge": "No Escape", "description": "In a single set, win with three different characters."},
        {"badge": "Specialism", "description": "Win five games in a row with the same character."},
        {"badge": "Awakening", "description": "In one set, lose two games and then three-stock the other player during the third game."},
        {"badge": "Fight for My Friends", "description": "Have all characters from the Fire Emblem series above 1,000 ELO concurrently."},
        {"badge": "Randomizer", "description": "Win three games in a row with randomly selected characters."},
        {"badge": "Lifestream", "description": "Three-stock Cloud while playing as Sephiroth."},
        {"badge": "To New Heights", "description": "Gain more than 50 ELO rating from a single match."},
        {"badge": "PACKUN FLOWER", "description": "Win a game as Packun Flower."},
        {"badge": "Into Darkness", "description": "Reach 1,300 ELO rating with a character that has a darkness ability (Ganondorf, Hero, Joker, Mewtwo, Olimar, Piranha Plant, Robin, Ridley, Sephiroth)."},
        {"badge": "Split Timeline", "description": "During the same set, win a game as young Link, Toon Link, and Link (in that order)."},
        {"badge": "At Your Mercy", "description": "Win a game after letting your opponent choose your character."},
        {"badge": "From the Grave", "description": "Three-stock another player while using a character with an ELO rating of less than 1,000."},
        {"badge": "Usurper", "description": "Win a game against someone whose global ELO rating is at least (100/300/500/1,000) higher than yours."},
        {"badge": "Versus Myself", "description": "During the same set, win three games in a row as mirror matches."},
    ]
    return render_template('player_badges.html', badges=badges)





@app.route("/matches")
@requires_auth
def matches():
    data = load_players()
    last = load_last_result() or {}   # <-- FIXED
    player_list = sorted(list(data.keys()))

    return render_template(
        "index.html",
        players=data,
        characters=CHARACTERS,
        last=last,
        last_player1=last.get("last_player1", ""),
        last_player2=last.get("last_player2", ""),
        last_char1=last.get("last_char1", ""),
        last_char2=last.get("last_char2", ""),
        player_list=player_list
    )


@app.route("/")
def home_redirect():
    return redirect(url_for("leaderboard"))




@app.route("/leaderboard")
def leaderboard():
    data = load_players()

    # Load last result safely
    try:
        with open(LAST_RESULT_FILE, "r") as f:
            last_result = json.load(f)
    except:
        last_result = None

    # Build leaderboard rows
    rows = []
    for player, char_map in data.items():
        diffs = [(elo - 1000) for elo in char_map.values() if elo != 1000]
        global_elo = sum(diffs) if diffs else 0
        rows.append((player, global_elo, char_map))

    # Sort by ELO (descending)
    rows.sort(key=lambda x: x[1], reverse=True)

    # Build rank lookup table: {"Will": 1, "Nick R": 2, ...}
    rank_map = {player: i + 1 for i, (player, _, _) in enumerate(rows)}

    # Load match log once
    log = load_match_log()

        # Compute win streaks
    from collections import defaultdict

    def compute_win_streaks(match_log):
        streaks = defaultdict(int)

        for m in match_log:
            winner = m["p1"] if m["winner"] == "p1" else m["p2"]
            loser = m["p2"] if winner == m["p1"] else m["p1"]

            streaks[winner] += 1
            streaks[loser] = 0

        return streaks

    win_streaks = compute_win_streaks(log)


    # Last 20 matches, newest → oldest
    recent_matches = log[-20:][::-1]

    # Render page
    return render_template(
    "leaderboard.html",
    rows=rows,
    last_result=last_result,
    recent_matches=recent_matches,
    rank_map=rank_map,
    admin_usernames=ADMIN_USERNAMES,
    win_streaks=win_streaks
)
















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
    

@app.route("/sync")
def sync_now():
    queue_push("Manual sync request")
    return "Manual sync triggered. Check /admin for status."

@app.route("/add_match", methods=["POST"])
@requires_auth
def add_match():

    p1 = request.form["player1"]
    c1 = request.form["p1_character"]
    p2 = request.form["player2"]
    c2 = request.form["p2_character"]
    winner = request.form["winner"]

    # Three-stock checkbox
    three_stock = request.form.get("three_stock") == "on"

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

    # --- NORMAL ELO UPDATE ---
    new1, new2 = calculate_elo(old1, old2, winner)

    # the change (before three-stock adjustments)
    change1 = new1 - old1
    change2 = new2 - old2

    # --- CHECK GLOBAL RANKINGS ---
    players_data = load_players()

    def global_rank(player_name):
        if player_name not in players_data:
            return 999999  # safely last
        ratings = players_data[player_name].values()
        return sum(r - 1000 for r in ratings if r != 1000)

    p1_global = global_rank(p1)
    p2_global = global_rank(p2)

    # --- DETERMINE WINNER/LOSER GLOBAL RATINGS ---
    if winner == "p1":
        winner_global = p1_global
        loser_global = p2_global
    else:
        winner_global = p2_global
        loser_global = p1_global

    # --- APPLY THREE-STOCK DOUBLING ONLY WHEN VALID ---
    if three_stock and winner_global < loser_global:
        change1 *= 2
        change2 *= 2
        new1 = old1 + change1
        new2 = old2 + change2

    # Apply min rating of 800
    new1 = max(800, round(new1))
    new2 = max(800, round(new2))

    # Save final ratings
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
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "p1": p1,
        "c1": c1,
        "new1": new1,
        "diff1": new1 - old1,
        "p2": p2,
        "c2": c2,
        "new2": new2,
        "diff2": new2 - old2,
        "winner": winner,
        "three_stock": three_stock
    })


    save_match_log(log)

    # Auto commit/push
    queue_push("Auto-update from match submission")

    return redirect(url_for("matches"))




@app.route("/admin")
@requires_auth
def admin_panel():
    return render_template(
        "admin.html",
        queue_length=len(push_queue),
        pushing_status="Running" if is_pushing else "Idle",
        push_log=push_log
    )



if __name__ == "__main__":
    app.run(debug=True, port=5001)
