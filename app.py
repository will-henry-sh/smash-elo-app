from flask import Flask, render_template, request, redirect, url_for
import json
import os
import subprocess
import threading
from functools import wraps
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Response

APP_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(APP_DIR, ".env"))
except ImportError:
    print("python-dotenv not installed, using environment variables directly")

print("RUNNING FROM:", os.getcwd())
print("APP FILE:", __file__)
print(">>> LOADED FLASK APP FROM:", __file__)



app = Flask(__name__)

push_queue = []
is_pushing = False
push_log = []  # Stores recent push messages
MAX_LOGS = 20
# Admin login credentials loaded from environment variables
def load_admin_credentials():
    """Load admin credentials from environment variables."""
    admin_users = {}
    for i in range(1, 10):  # Support up to 9 admin users
        env_var = os.getenv(f'ADMIN_USER_{i}')
        if env_var and ':' in env_var:
            username, password = env_var.split(':', 1)
            admin_users[username] = password

    admin_names_str = os.getenv('ADMIN_NAMES', '')
    admin_names = [name.strip() for name in admin_names_str.split(',') if name.strip()]

    if not admin_users:
        raise RuntimeError(
            "No admin credentials found. Set ADMIN_USER_1..ADMIN_USER_9 in your environment or .env file."
        )

    # Always use the original admin names for the key icons
    if not admin_names:
        admin_names = ["Will", "Colton", "Nick R"]

    return admin_users, admin_names

ADMIN_USERS, ADMIN_USERNAMES = load_admin_credentials()
print(f"Loaded {len(ADMIN_USERS)} admin users")
ADMIN_PANEL_USERNAME = "bunnyslave"

DECAY_START_DAYS = 14
DECAY_PER_DAY = 2      # total global decay per day
CHAR_FLOOR = 1000

def apply_decay_to_player(player_data):
    """Safely decays only real character ratings."""
    
    last_played_str = player_data.get("last_played")
    if not last_played_str:
        return

    try:
        last_played = datetime.strptime(last_played_str, "%Y-%m-%d").date()
    except:
        return

    today = datetime.now().date()
    inactive_days = (today - last_played).days

    if inactive_days <= DECAY_START_DAYS:
        return

    days_of_decay = inactive_days - DECAY_START_DAYS

    # Only decay TRUE characters
    char_keys = [
        c for c, v in player_data.items()
        if c in CHARACTERS and isinstance(v, (int, float))
    ]

    if not char_keys:
        return

    # decay per character per day
    decay_per_char = DECAY_PER_DAY / len(char_keys)
    decay_per_char = int(decay_per_char) if decay_per_char >= 1 else 1

    total_decay = decay_per_char * days_of_decay

    for c in char_keys:
        new_val = player_data[c] - total_decay
        player_data[c] = max(CHAR_FLOOR, int(new_val))


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
MOMS_HOUSE_FILE = f"{DATA_DIR}/moms_house.json"
MOMS_HOUSE_LOG_FILE = f"{DATA_DIR}/moms_house_log.json"
MOMS_HOUSE_LAST_FILE = f"{DATA_DIR}/moms_house_last_result.json"
SEASONS_FILE = f"{DATA_DIR}/seasons.json"


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

def load_moms_house():
    if not os.path.exists(MOMS_HOUSE_FILE):
        return {}
    with open(MOMS_HOUSE_FILE, "r") as f:
        return json.load(f)

def save_moms_house(data):
    with open(MOMS_HOUSE_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_moms_house_log():
    if not os.path.exists(MOMS_HOUSE_LOG_FILE):
        return []
    with open(MOMS_HOUSE_LOG_FILE, "r") as f:
        return json.load(f)

def save_moms_house_log(log):
    with open(MOMS_HOUSE_LOG_FILE, "w") as f:
        json.dump(log, f, indent=4)

def load_moms_house_last_result():
    if not os.path.exists(MOMS_HOUSE_LAST_FILE):
        return {}
    with open(MOMS_HOUSE_LAST_FILE, "r") as f:
        return json.load(f)

def save_moms_house_last_result(result):
    with open(MOMS_HOUSE_LAST_FILE, "w") as f:
        json.dump(result, f, indent=4)


def _default_seasons_data():
    return {
        "current_season": {
            "number": 1,
            "started_at": None,
            "match_start_index": 0
        },
        "archive": []
    }


def _safe_int(value, fallback):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def load_seasons():
    if not os.path.exists(SEASONS_FILE):
        return _default_seasons_data()

    try:
        with open(SEASONS_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        return _default_seasons_data()

    if not isinstance(data, dict):
        return _default_seasons_data()

    current = data.get("current_season") or {}
    archive = data.get("archive")

    if not isinstance(current, dict):
        current = {}
    if not isinstance(archive, list):
        archive = []

    return {
        "current_season": {
            "number": max(1, _safe_int(current.get("number", 1), 1)),
            "started_at": current.get("started_at"),
            "match_start_index": max(0, _safe_int(current.get("match_start_index", 0), 0))
        },
        "archive": archive
    }


def save_seasons(data):
    with open(SEASONS_FILE, "w") as f:
        json.dump(data, f, indent=4)


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
    "Random", "Robin", "Rosalina and Luma", "Roy", "Ryu",
    "Samus", "Sephiroth", "Sheik", "Shulk", "Simon",
    "Snake", "Sonic", "Sora", "Squirtle", "Steve",
    "Terry", "Toon Link", "Villager", "Wario",
    "Wii Fit Trainer", "Wolf", "Yoshi", "Young Link",
    "Zelda", "Zero Suit Samus"
])


def extract_character_ratings(player_data):
    return {
        char: rating
        for char, rating in player_data.items()
        if char in CHARACTERS and isinstance(rating, (int, float))
    }


def build_leaderboard_rows(players_data):
    rows = []
    for player, player_data in players_data.items():
        char_map = extract_character_ratings(player_data)
        global_elo = sum(rating - 1000 for rating in char_map.values())
        rows.append((player, global_elo, char_map))

    rows.sort(key=lambda row: row[1], reverse=True)
    return rows


def get_best_character(player_data):
    char_map = extract_character_ratings(player_data)
    if not char_map:
        return None

    best_name = max(char_map, key=lambda name: char_map[name])
    return {
        "name": best_name,
        "rating": char_map[best_name]
    }


def format_display_date(value):
    if not value:
        return None

    for date_format in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, date_format)
            return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
        except ValueError:
            continue

    if isinstance(value, str) and " " in value:
        return value.split(" ", 1)[0]

    return value


def build_lifetime_archive_view(archived_seasons):
    player_totals = {}

    for season in archived_seasons:
        for row in season.get("rows", []):
            player = row.get("player")
            if not player:
                continue

            player_entry = player_totals.setdefault(player, {
                "player": player,
                "rating": 0,
                "best_character": None
            })

            player_entry["rating"] += _safe_int(row.get("rating"), 0)

            best_character = row.get("best_character") or {}
            best_rating = _safe_int(best_character.get("rating"), 0)
            current_best = player_entry["best_character"]

            if best_character.get("name") and (
                current_best is None or best_rating > _safe_int(current_best.get("rating"), 0)
            ):
                player_entry["best_character"] = {
                    "name": best_character.get("name"),
                    "rating": best_rating
                }

    rows = sorted(player_totals.values(), key=lambda row: row["rating"], reverse=True)

    return {
        "title": "Lifetime",
        "started_at": archived_seasons[-1].get("started_at") if archived_seasons else None,
        "closed_at": archived_seasons[0].get("closed_at") if archived_seasons else None,
        "match_count": sum(_safe_int(season.get("match_count"), 0) for season in archived_seasons),
        "rows": rows
    }


def get_current_season_log(match_log, seasons_data):
    start_index = seasons_data.get("current_season", {}).get("match_start_index", 0)
    if not isinstance(start_index, int):
        start_index = 0
    start_index = max(0, min(start_index, len(match_log)))
    return match_log[start_index:]


def reset_live_ratings_for_new_season(players_data):
    reset_data = {}

    for player, player_data in players_data.items():
        reset_player = {}
        for key, value in player_data.items():
            if key in CHARACTERS and isinstance(value, (int, float)):
                reset_player[key] = 1000
            else:
                reset_player[key] = value
        reset_data[player] = reset_player

    return reset_data


# -----------------------------
# ELO Calculation
# -----------------------------

# -----------------------------
# NEW MATCHMAKING ELO SYSTEM
# -----------------------------

BASE_WIN = 30
BASE_LOSS = 15
MOMS_HOUSE_K = 24

def combined_value(char_rating, global_rating):
    return char_rating * 0.7 + global_rating * 0.3

def expected_score(my_combined, opp_combined):
    return 1 / (1 + 10 ** ((opp_combined - my_combined) / 400))


def calculate_elo_custom(
    p1_char, p2_char,
    p1_global, p2_global,
    winner
):
    BASE_WIN = 30   # keep your base values
    # BASE_LOSS removed — we now compute it dynamically for balance

    # Combined character+global weighted values
    c1 = p1_char * 0.7 + p1_global * 0.3
    c2 = p2_char * 0.7 + p2_global * 0.3

    # Expected outcomes
    exp_p1 = 1 / (1 + 10 ** ((c2 - c1) / 400))
    exp_p2 = 1 - exp_p1

    # Choose the expected score for the actual winner
    expected = exp_p1 if winner == "p1" else exp_p2

    # --- Winner multiplier based on upset magnitude ---
    if expected < 0.01:
        winner_mult = 1 + 10.0 * (0.5 - expected)     # insane upset
    elif expected < 0.10:
        winner_mult = 1 + 6.0 * (0.5 - expected)      # huge upset
    elif expected < 0.30:
        winner_mult = 1 + 3.0 * (0.5 - expected)      # big upset
    else:
        winner_mult = 1 + 1.2 * (0.5 - expected)      # normal match

    # GAIN is based on winner multiplier
    gain = round(BASE_WIN * winner_mult)

    # LOSS is ~90% of gain (Showdown-style symmetry)
    loss = round(gain * 0.9)

    # Apply result
    if winner == "p1":
        new_p1 = p1_char + gain
        new_p2 = p2_char - loss
    else:
        new_p1 = p1_char - loss
        new_p2 = p2_char + gain

    # Floor ratings at 1000
    return max(1000, new_p1), max(1000, new_p2)


def calculate_moms_house_deltas(placements, ratings):
    """Pairwise multiplayer Elo: higher placement beats lower placement."""
    deltas = {name: 0 for name in placements}
    for i, winner in enumerate(placements):
        for loser in placements[i + 1:]:
            r_w = ratings[winner]
            r_l = ratings[loser]
            expected_w = 1 / (1 + 10 ** ((r_l - r_w) / 400))
            change = MOMS_HOUSE_K * (1 - expected_w)
            deltas[winner] += change
            deltas[loser] -= change
    return deltas




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


def requires_admin_panel_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if (
            not auth
            or not check_auth(auth.username, auth.password)
            or auth.username != ADMIN_PANEL_USERNAME
        ):
            return authenticate()
        return f(*args, **kwargs)
    return decorated



# -----------------------------
# Routes
# -----------------------------
@app.route('/badges')
def badges():
    badges = [
        {"badge": "Ambition", "description": "Win (5/15/25) matches in a row"},
        {"badge": "Drowning Lessons", "description": "Lose 10 matches in a row"},
        {"badge": "Game Set", "description": "Win (10/50/100/500) total matches) "},
        {"badge": "Dominator", "description": "Three-stock another player"},
        {"badge": "Devastator", "description": "Three-stock another player three times in a row in a set"},
        {"badge": "Kidnapper", "description": "Win a game by using Ganondorf's Flame Choke"},
        {"badge": "Global Enthusiasm", "description": "Get ranked with every character"},
        {"badge": "Sky Full of Stars", "description": "Reach 2,000 global ELO ranking"},
        {"badge": "No Escape", "description": "In a single set, win with three different characters"},
        {"badge": "Specialism", "description": "Win five games in a row with the same character"},
        {"badge": "Awakening", "description": "In one set, lose two games and then three-stock the other player during the third game"},
        {"badge": "Fight for My Friends", "description": "Have all characters from the Fire Emblem series above 1,000 ELO concurrently"},
        {"badge": "Randomizer", "description": "Win three games in a row with randomly selected characters"},
        {"badge": "Lifestream", "description": "Three-stock Cloud while playing as Sephiroth"},
        {"badge": "To New Heights", "description": "Gain more than 50 ELO rating from a single match"},
        {"badge": "PACKUN FLOWER", "description": "Win a game as Packun Flower"},
        {"badge": "Into Darkness", "description": "Reach 1,500 ELO rating with a character that has a darkness ability (Ganondorf, Hero, Joker, Mewtwo, Olimar, Piranha Plant, Robin, Ridley, Sephiroth)"},
        {"badge": "Split Timeline", "description": "During the same set, win a game as young Link, Toon Link, and Link (in that order"},
        {"badge": "At Your Mercy", "description": "Win a game after letting your opponent choose your character"},
        {"badge": "From the Grave", "description": "Three-stock another player while using your worst-rated character"},
        {"badge": "Usurper", "description": "Win a game against someone whose global ELO rating is at least 1,000 higher than yours"},
        {"badge": "Versus Myself", "description": "During the same set, win three games in a row as mirror matches"},
        {"badge": "Earth Badge", "description": "Get Pokemon Trainer to 1,500 ELO rating"},
        {"badge": "Bloodlust", "description": "Beat three different players without losing a game"},
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
        last_winner=last.get("last_winner", "p1"),
        player_list=player_list
    )


@app.route("/")
def home_redirect():
    return redirect(url_for("leaderboard"))




@app.route("/leaderboard")
def leaderboard():
    data = load_players()
    seasons_data = load_seasons()

    # --- APPLY ELO DECAY SAFELY ---
    for pname, pdata in data.items():
        apply_decay_to_player(pdata)

    save_players(data)


    # Load last result safely
    try:
        with open(LAST_RESULT_FILE, "r") as f:
            last_result = json.load(f)
    except:
        last_result = None

    log = load_match_log()
    season_log = get_current_season_log(log, seasons_data)
    rows = build_leaderboard_rows(data)

    # Build rank lookup table: {"Will": 1, "Nick R": 2, ...}
    rank_map = {player: i + 1 for i, (player, _, _) in enumerate(rows)}

    # Compute current-season win streaks
    from collections import defaultdict

    def compute_win_streaks(match_log):
        streaks = defaultdict(int)

        for m in match_log:
            winner = m["p1"] if m["winner"] == "p1" else m["p2"]
            loser = m["p2"] if winner == m["p1"] else m["p1"]

            streaks[winner] += 1
            streaks[loser] = 0

        return streaks

    win_streaks = compute_win_streaks(season_log)


    # Last 20 matches, newest → oldest
    # --- Build Recent Matches Sorted by Timestamp ---
    from datetime import datetime

    def parse_time(entry):
        ts = entry.get("timestamp", "")
        try:
            # preferred 12-hour timestamp
            return datetime.strptime(ts, "%Y-%m-%d %I:%M %p")
        except:
            try:
                # legacy 24-hour timestamp
                return datetime.strptime(ts, "%Y-%m-%d %H:%M")
            except:
                # Handle missing or invalid timestamps
                return datetime.min   # pushes old/no-timestamp entries to the bottom

    # Sort all matches chronologically
    log_sorted = sorted(season_log, key=parse_time)

    # Take the last 20 (newest), then reverse so newest → oldest
    recent_matches = log_sorted[-20:][::-1]


    # Render page
    return render_template(
    "leaderboard.html",
    rows=rows,
    last_result=last_result,
    recent_matches=recent_matches,
    rank_map=rank_map,
    admin_usernames=ADMIN_USERNAMES,
    win_streaks=win_streaks,
    current_season=seasons_data["current_season"],
    archived_seasons=seasons_data["archive"]
)
















@app.route("/player/<name>")
def player_stats(name):
    data = load_players()
    match_log = load_match_log()

    if name not in data:
        return f"Player '{name}' not found.", 404

    all_players = sorted(data.keys())  # <-- add this
    # Pull badges safely
    badges_list = data[name].get("badges", [])

    # Remove badges entry from character ratings
    char_map = extract_character_ratings(data[name])

    total_chars = len(char_map)

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

    # ----- Manual Badges -----
    player_badges = []

    badge_folder = "static/badges"
    player_badges = []

    # Custom descriptions for each badge ID (keys MUST match file names)
    CUSTOM_DESCRIPTIONS = {

        # --- TIERED BADGES ---
        "ambition1": "Win 5 matches in a row",
        "ambition2": "Win 15 matches in a row",
        "ambition3": "Win 25 matches in a row",

        "gameset1": "Win 10 total matches",
        "gameset2": "Win 50 total matches",
        "gameset3": "Win 100 total matches",
        "gameset4": "Win 500 total matches",

        # --- SINGLE ACHIEVEMENT BADGES ---
        "drowning_lessons": "Lose 10 matches in a row",
        "bloodlust": "Beat three different players without losing a game",
        "dominator": "Three-stock another player",
        "devastator": "Three-stock another player three times in a row during one set",
        "kidnapper": "Win a game by using Ganondorf's Flame Choke",
        "global_enthusiasm": "Get ranked with every character",
        "sky_full_of_stars": "Reach 2,000 global ELO",
        "no_escape": "Win a set using three different characters",
        "specialism": "Win five games in a row with the same character",
        "awakening": "Lose two games in a set, then three-stock your opponent in game three",
        "fight_for_my_friends": "Have all Fire Emblem characters above 1,000 ELO",
        "randomizer": "Win three games in a row with randomly selected characters",
        "lifestream": "Three-stock Cloud while playing as Sephiroth",

        "packun_flower": "Win a game as Packun Flower",

        "into_darkness": "Reach 1,500 ELO with a character that uses darkness abilities",
        "split_timeline": "Win a set as Young Link, then Toon Link, then Link in order",
        "at_your_mercy": "Win a game after letting your opponent choose your character",
        "from_the_grave": "Three-stock another player using your lowest-rated character",
        "usurper": "Defeat a player whose global ELO is at least 1,000 higher than yours",
        "versus_myself": "Win three mirror matches in a row in the same set",
        "earth_badge": "Reach 1,500 ELO with Pokémon Trainer"
    }


    for raw_id in data[name].get("badges", []):

        # Normalize badge ID for dictionary + file lookup
        clean_id = raw_id.strip().lower().replace(" ", "_")

        # Expected file name
        file_name = f"{clean_id}.png"
        full_path = os.path.join(badge_folder, file_name)

        if not os.path.exists(full_path):
            continue  # skip missing icons

        # Strip tier numbers from tiered badge names
        base_id = ''.join(ch for ch in clean_id if not ch.isdigit())

        pretty = " ".join(word.capitalize() for word in base_id.split("_"))


        # SPECIAL CASE → PACKUN FLOWER SHOULD BE ALL CAPS
        if clean_id == "packun_flower":
            pretty = "PACKUN FLOWER"

        # --- DESCRIPTION ---
        description = CUSTOM_DESCRIPTIONS.get(
            clean_id,
            f"{pretty} badge earned."
        )

        player_badges.append({
            "name": pretty,
            "description": description,
            "icon": f"/static/badges/{file_name}"
        })









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
        win_rate=win_rate,
        badges=player_badges,
        all_players=all_players
    )


@app.route("/lifetime-ratings")
def lifetime_ratings():
    seasons_data = load_seasons()
    archived_seasons = list(reversed(seasons_data.get("archive", [])))
    season_options = [season.get("number") for season in archived_seasons if season.get("number") is not None]
    requested_view = request.args.get("season", "lifetime")

    selected_season = None
    visible_seasons = []

    if requested_view != "lifetime":
        requested_season = _safe_int(requested_view, None)
        if requested_season in season_options:
            selected_season = requested_season
            visible_seasons = [
                season for season in archived_seasons
                if season.get("number") == selected_season
            ]

    if not visible_seasons and archived_seasons:
        visible_seasons = [build_lifetime_archive_view(archived_seasons)]

    visible_seasons = [
        {
            **season,
            "display_date": format_display_date(season.get("closed_at"))
        }
        for season in visible_seasons
    ]

    return render_template(
        "lifetime_ratings.html",
        archived_seasons=visible_seasons,
        season_options=season_options,
        selected_season=selected_season,
        current_season=seasons_data["current_season"]
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
@requires_admin_panel_auth
def sync_now():
    queue_push("Manual sync request")
    return "Manual sync triggered. Check /admin for status."


@app.route("/start_new_season", methods=["POST"])
@requires_admin_panel_auth
def start_new_season():
    players_data = load_players()
    match_log = load_match_log()
    seasons_data = load_seasons()
    current_season = seasons_data["current_season"]
    now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M %p")

    snapshot_rows = [
        {
            "player": player,
            "rating": rating,
            "best_character": get_best_character(players_data.get(player, {}))
        }
        for player, rating, _ in build_leaderboard_rows(players_data)
    ]

    season_log = get_current_season_log(match_log, seasons_data)
    seasons_data["archive"].append({
        "number": current_season["number"],
        "started_at": current_season.get("started_at"),
        "closed_at": now,
        "match_count": len(season_log),
        "rows": snapshot_rows
    })

    seasons_data["current_season"] = {
        "number": current_season["number"] + 1,
        "started_at": now,
        "match_start_index": len(match_log)
    }

    save_seasons(seasons_data)
    save_players(reset_live_ratings_for_new_season(players_data))
    save_last_result({})

    queue_push(f"Archived Season {current_season['number']} and started Season {current_season['number'] + 1}")
    return redirect(url_for("admin_panel"))

def compute_global_elo(player_name, players_data):
    """Returns total global ELO offset (sum of character deviations from 1000)."""
    if player_name not in players_data:
        return 0

    return sum(
        (elo - 1000)
        for elo in players_data[player_name].values()
        if isinstance(elo, (int, float))  # only count numeric ELO values
    )



@app.route("/add_match", methods=["GET", "POST"])
@requires_auth
def add_match():
    if request.method == "GET":
        return redirect(url_for("matches"))

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

    # -------------------------------------------------
    # NEW CUSTOM ELO UPDATE (replaces old calculate_elo)
    # -------------------------------------------------

    players_data = load_players()


    p1_global = compute_global_elo(p1, players_data)
    p2_global = compute_global_elo(p2, players_data)


    # New elo calculation
    new1, new2 = calculate_elo_custom(
        old1, old2,
        p1_global, p2_global,
        winner
    )

    # Change amount (needed for 3-stock logic)
    change1 = new1 - old1
    change2 = new2 - old2

    # -------------------------------------------------
    # REMAINDER OF ROUTE IS UNCHANGED
    # -------------------------------------------------


    p1_global_rank = compute_global_elo(p1, players_data)
    p2_global_rank = compute_global_elo(p2, players_data)


    # --- DETERMINE WINNER/LOSER GLOBAL RATINGS ---
    if winner == "p1":
        winner_global = p1_global_rank
        loser_global = p2_global_rank
    else:
        winner_global = p2_global_rank
        loser_global = p1_global_rank


    # --- NEW THREE-STOCK LOGIC ---
    if three_stock:
        if winner == "p1":
            change1 *= 2          # winner bonus
            new1 = old1 + change1
            new2 = old2 + change2 # loser normal loss
        else:
            change2 *= 2          # winner bonus
            new2 = old2 + change2
            new1 = old1 + change1 # loser normal loss






    # Apply min rating of 1000
    new1 = max(1000, round(new1))
    new2 = max(1000, round(new2))

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
        "last_char2": c2,
        "last_winner": winner
    })

    # Log match history
    log = load_match_log()
    log.append({
        "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M %p"),
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
@requires_admin_panel_auth
def admin_panel():
    seasons_data = load_seasons()
    return render_template(
        "admin.html",
        queue_length=len(push_queue),
        pushing_status="Running" if is_pushing else "Idle",
        push_log=push_log,
        current_season=seasons_data["current_season"],
        archived_count=len(seasons_data["archive"])
    )

@app.route("/api/matchup/<player>/<opponent>")
def api_matchup(player, opponent):
    log = load_match_log()

    wins = 0
    losses = 0

    for m in log:
        players_in_match = {m["p1"], m["p2"]}

        if {player, opponent} == players_in_match:
            winner_name = m["p1"] if m["winner"] == "p1" else m["p2"]
            if winner_name == player:
                wins += 1
            else:
                losses += 1

    total = wins + losses
    win_rate = round((wins / total) * 100, 1) if total > 0 else 0

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate
    }


@app.route("/moms-house")
@requires_auth
def moms_house():
    players_data = load_players()
    moms_data = load_moms_house()
    last = load_moms_house_last_result() or {}
    player_list = sorted(set(players_data.keys()) | set(moms_data.keys()))

    # Ensure every known player has a Mom's House rating
    updated = False
    for name in player_list:
        if name not in moms_data:
            moms_data[name] = 1000
            updated = True
    if updated:
        save_moms_house(moms_data)

    return render_template(
        "moms_house.html",
        player_list=player_list,
        last=last,
        last_placements=last.get("placements", [])
    )


@app.route("/add_moms_house", methods=["POST"])
@requires_auth
def add_moms_house():
    # Collect up to 8 placements in order (1..8)
    placements = []
    seen = set()
    for i in range(1, 9):
        name = request.form.get(f"place_{i}", "").strip()
        if not name:
            continue
        if name in seen:
            return f"Duplicate player '{name}' in placements.", 400
        seen.add(name)
        placements.append(name)

    if len(placements) < 2:
        return "Need at least 2 players to submit a match.", 400

    data = load_moms_house()
    # Initialize players at 1000
    for name in placements:
        if name not in data:
            data[name] = 1000

    # Snapshot ratings before updates
    ratings_before = {name: data[name] for name in placements}
    deltas = calculate_moms_house_deltas(placements, ratings_before)

    # Apply deltas with floor at 1000
    for name in placements:
        data[name] = max(1000, round(ratings_before[name] + deltas[name]))

    save_moms_house(data)

    # Use applied deltas after floor so losses don't exceed 1000 floor
    applied_deltas = {name: data[name] - ratings_before[name] for name in placements}

    # Log result
    log = load_moms_house_log()
    timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M %p")
    log.append({
        "timestamp": timestamp,
        "placements": placements,
        "before": ratings_before,
        "after": {name: data[name] for name in placements},
        "delta": applied_deltas
    })
    save_moms_house_log(log)

    save_moms_house_last_result({
        "timestamp": timestamp,
        "placements": placements,
        "after": {name: data[name] for name in placements},
        "delta": applied_deltas
    })

    queue_push("Auto-update from Mom's House submission")
    return redirect(url_for("moms_house"))


@app.route("/scoreboard")
def scoreboard():
    data = load_moms_house()
    players_data = load_players()
    player_list = sorted(set(players_data.keys()) | set(data.keys()))

    updated = False
    for name in player_list:
        if name not in data:
            data[name] = 1000
            updated = True
    if updated:
        save_moms_house(data)

    # Compute win streaks from Mom's House logs (1st place streaks)
    from collections import defaultdict
    streaks = defaultdict(int)
    log = load_moms_house_log()
    for entry in log:
        placements = entry.get("placements", [])
        if not placements:
            continue
        winner = placements[0]
        streaks[winner] += 1
        for loser in placements[1:]:
            streaks[loser] = 0

    rows = sorted(data.items(), key=lambda x: x[1], reverse=True)
    return render_template("scoreboard.html", rows=rows, win_streaks=streaks)



if __name__ == "__main__":
    app.run(debug=True, port=5001)
