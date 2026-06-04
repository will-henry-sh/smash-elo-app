from flask import Flask, render_template, request, redirect, url_for
import json
import os
import subprocess
import threading
import difflib
from functools import wraps
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Response
from io import BytesIO

from PIL import Image, ImageFilter, ImageOps

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
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
MAX_OCR_IMAGE_DIMENSION = 1600
TESSERACT_TIMEOUT_SECONDS = 4

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
            subprocess.run(["git", "add", "-u"], check=True, cwd=APP_DIR)

            diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=APP_DIR)
            if diff_check.returncode == 0:
                msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No changes to commit ({commit_message})"
                print(msg)
                push_log.append(msg)
                if len(push_log) > MAX_LOGS:
                    push_log.pop(0)
                continue

            subprocess.run(["git", "commit", "-m", commit_message], check=True, cwd=APP_DIR)
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True, cwd=APP_DIR)
            subprocess.run(["git", "push", "origin", "main"], check=True, cwd=APP_DIR)

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


pull_log = []


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
PLAYER_TAGS_FILE = f"{DATA_DIR}/player_tags.json"


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

def load_player_tags():
    if not os.path.exists(PLAYER_TAGS_FILE):
        return {}
    with open(PLAYER_TAGS_FILE, "r") as f:
        return json.load(f)

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
    "Byleth", "Captain Falcon", "Chrom",
    "Cloud", "Corrin", "Daisy", "Dark Pit", "Dark Samus",
    "Diddy Kong", "Donkey Kong", "Dr. Mario", "Duck Hunt",
    "Falco", "Fox", "Ganondorf", "Greninja", "Hero",
    "Ice Climbers", "Ike", "Incineroar", "Inkling",
    "Isabelle", "Jigglypuff", "Joker",
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
    "Snake", "Sonic", "Sora", "Steve",
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
        bonus = player_data.get("_elo_bonus", 0)
        if isinstance(bonus, (int, float)):
            global_elo += int(bonus)
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


def apply_random_modifier(character_name, change_amount):
    if character_name != "Random":
        return change_amount

    if change_amount > 0:
        return round(change_amount * 1.5)

    if change_amount < 0:
        return round(change_amount * 0.8)

    return 0


def normalize_lookup_value(value):
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def canonicalize_character_name(character_name):
    character_aliases = {
        "charizard": "Pokemon Trainer",
        "ivysaur": "Pokemon Trainer",
        "squirtle": "Pokemon Trainer",
        "mythra": "Pyra/Mythra",
        "pyra": "Pyra/Mythra",
    }
    return character_aliases.get(normalize_lookup_value(character_name), character_name)


def build_player_aliases(player_name, player_tag_map=None):
    aliases = {player_name}
    parts = player_name.split()

    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        aliases.update({
            f"{first} {last[0]}",
            f"{first}{last[0]}",
            f"{first}-{last[0]}",
            f"{first}_{last[0]}",
        })

    if player_tag_map:
        for tag, mapped_player in player_tag_map.items():
            if mapped_player == player_name:
                aliases.add(tag)
                for part in tag.split():
                    cleaned_part = part.strip()
                    if len(cleaned_part) >= 4:
                        aliases.add(cleaned_part)

    return {alias for alias in aliases if alias}


def build_character_aliases(character_name, _alias_context=None):
    canonical_name = canonicalize_character_name(character_name)
    aliases = {canonical_name}
    normalized = normalize_lookup_value(canonical_name)

    special_aliases = {
        "bowserjr": {"Bowser Jr."},
        "drmario": {"Dr. Mario", "Doctor Mario"},
        "kingkrool": {"King K. Rool", "King Krool"},
        "mrgameandwatch": {"Mr. Game and Watch", "Mr Game and Watch", "Game & Watch", "Game and Watch"},
        "pacman": {"Pac-Man", "Pac Man"},
        "piranhaplant": {"Piranha Plant", "Plant", "Packun", "Packun Flower"},
        "pokemontrainer": {"Pokemon Trainer", "PokemonTrainer", "Charizard", "Squirtle", "Ivysaur"},
        "pyramythra": {"Pyra/Mythra", "Pyra Mythra", "Aegis", "Pyra", "Mythra"},
        "rob": {"R.O.B", "ROB"},
        "rosalinaandluma": {"Rosalina and Luma", "Rosalina & Luma"},
        "toonlink": {"Toon Link"},
        "wiifittrainer": {"Wii Fit Trainer", "WiiFitTrainer"},
        "younglink": {"Young Link"},
        "zerosuitsamus": {"Zero Suit Samus", "ZSS"},
    }

    aliases.update(special_aliases.get(normalized, set()))
    return {alias for alias in aliases if alias}


def resolve_best_match(raw_value, candidates, alias_builder, alias_context=None):
    if not raw_value:
        return {
            "matched": None,
            "score": 0.0,
            "raw": raw_value or "",
            "ambiguous": False
        }

    raw_normalized = normalize_lookup_value(raw_value)
    best_match = None
    best_score = 0.0
    second_score = 0.0

    for candidate in candidates:
        for alias in alias_builder(candidate, alias_context):
            alias_normalized = normalize_lookup_value(alias)
            if not alias_normalized:
                continue

            if alias_normalized == raw_normalized:
                score = 1.0
            elif min(len(raw_normalized), len(alias_normalized)) >= 4 and (
                raw_normalized in alias_normalized or alias_normalized in raw_normalized
            ):
                score = 0.94
            else:
                score = difflib.SequenceMatcher(None, raw_normalized, alias_normalized).ratio()

            if score > best_score:
                second_score = best_score
                best_score = score
                best_match = candidate
            elif score > second_score:
                second_score = score

    return {
        "matched": best_match if best_score >= 0.62 else None,
        "score": round(best_score, 3),
        "raw": raw_value,
        "ambiguous": best_score < 0.8 or (best_score - second_score) < 0.08
    }


def resolve_direct_alias_match(raw_candidates, candidates, alias_builder, alias_context=None):
    best_result = None

    for raw_value in raw_candidates:
        raw_normalized = normalize_lookup_value(raw_value)
        if len(raw_normalized) < 3:
            continue

        for candidate in candidates:
            for alias in alias_builder(candidate, alias_context):
                alias_normalized = normalize_lookup_value(alias)
                if len(alias_normalized) < 3:
                    continue

                if raw_normalized == alias_normalized:
                    return {
                        "matched": candidate,
                        "score": 1.0,
                        "raw": raw_value,
                        "ambiguous": False
                    }

                if min(len(raw_normalized), len(alias_normalized)) >= 4 and (
                    raw_normalized in alias_normalized or alias_normalized in raw_normalized
                ):
                    result = {
                        "matched": candidate,
                        "score": 0.99,
                        "raw": raw_value,
                        "ambiguous": False
                    }
                    if best_result is None or len(alias_normalized) > len(normalize_lookup_value(best_result["raw"])):
                        best_result = result

    return best_result


def extract_response_text(response_payload):
    return ""


def crop_image(image, left, top, right, bottom):
    width, height = image.size
    box = (
        int(width * left),
        int(height * top),
        int(width * right),
        int(height * bottom),
    )
    return image.crop(box)


def upscale_for_ocr(image, scale=2.0):
    width, height = image.size
    return image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.Resampling.LANCZOS)


def downscale_for_ocr(image):
    width, height = image.size
    longest_side = max(width, height)
    if longest_side <= MAX_OCR_IMAGE_DIMENSION:
        return image

    scale = MAX_OCR_IMAGE_DIMENSION / float(longest_side)
    resized = (
        max(1, int(width * scale)),
        max(1, int(height * scale))
    )
    return image.resize(resized, Image.Resampling.LANCZOS)


def preprocess_text_region(image, threshold=180, invert=False):
    grayscale = ImageOps.grayscale(image)
    sharpened = grayscale.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)
    blurred = sharpened.filter(ImageFilter.GaussianBlur(radius=0.8))
    binary = blurred.point(lambda pixel: 255 if pixel >= threshold else 0, mode="1").convert("L")
    if invert:
        binary = ImageOps.invert(binary)
    return binary


def run_tesseract_ocr(image, psm=7, whitelist=None):
    config = ["tesseract", "stdin", "stdout", "--psm", str(psm)]
    if whitelist:
        config.extend(["-c", f"tessedit_char_whitelist={whitelist}"])

    try:
        with BytesIO() as output:
            image.save(output, format="PNG")
            proc = subprocess.run(
                config,
                input=output.getvalue(),
                capture_output=True,
                check=False,
                timeout=TESSERACT_TIMEOUT_SECONDS
            )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Tesseract OCR timed out while processing the image.") from exc

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Tesseract OCR failed: {stderr or 'unknown error'}")

    return proc.stdout.decode("utf-8", errors="replace").strip()


def normalize_ocr_text(value):
    return " ".join(value.replace("\n", " ").split()).strip(" .,:;|")


def collect_ocr_candidates(panel, region_specs, whitelist=None, include_invert=False):
    candidates = []
    seen = set()

    for left, top, right, bottom, scale, thresholds, psms in region_specs:
        region = upscale_for_ocr(crop_image(panel, left, top, right, bottom), scale)

        for psm in psms:
            raw_text = normalize_ocr_text(run_tesseract_ocr(region, psm=psm, whitelist=whitelist))
            if raw_text and raw_text not in seen:
                seen.add(raw_text)
                candidates.append(raw_text)

        for threshold in thresholds:
            processed = preprocess_text_region(region, threshold=threshold)
            image_variants = (processed,)
            if include_invert:
                image_variants = (processed, preprocess_text_region(region, threshold=threshold, invert=True))

            for image_variant in image_variants:
                for psm in psms:
                    text = normalize_ocr_text(run_tesseract_ocr(image_variant, psm=psm, whitelist=whitelist))
                    if text and text not in seen:
                        seen.add(text)
                        candidates.append(text)

    return candidates


def merge_unique_candidates(existing_candidates, new_candidates):
    merged = list(existing_candidates)
    seen = set(existing_candidates)
    for candidate in new_candidates:
        if candidate not in seen:
            seen.add(candidate)
            merged.append(candidate)
    return merged


def extract_first_placing_digit(value):
    for ch in value:
        if ch in {"1", "2"}:
            return int(ch)
    return 0


def detect_panel_placing(panel):
    candidate_specs = [
        (0.68, 0.00, 1.00, 0.22, 4.0, (120, 150, 180, 210), (10, 6)),
        (0.62, 0.00, 1.00, 0.20, 4.0, (120, 150, 180, 210), (10, 6)),
        (0.00, 0.00, 1.00, 0.20, 3.2, (150, 180), (6,)),
    ]

    seen_digits = []

    for left, top, right, bottom, scale, thresholds, psms in candidate_specs:
        region = upscale_for_ocr(crop_image(panel, left, top, right, bottom), scale)

        for psm in psms:
            raw_text = normalize_ocr_text(run_tesseract_ocr(region, psm=psm, whitelist="0123456789"))
            raw_digit = extract_first_placing_digit(raw_text)
            if raw_digit in {1, 2}:
                return raw_digit

        for threshold in thresholds:
            processed = preprocess_text_region(region, threshold=threshold)
            for psm in psms:
                processed_text = normalize_ocr_text(run_tesseract_ocr(processed, psm=psm, whitelist="0123456789"))
                digit = extract_first_placing_digit(processed_text)
                if digit in {1, 2}:
                    return digit
                if digit:
                    seen_digits.append(digit)

    return seen_digits[0] if seen_digits else 0


def resolve_best_match_from_candidates(raw_candidates, candidates, alias_builder, alias_context=None):
    filtered_candidates = [
        raw_value for raw_value in raw_candidates
        if len(normalize_lookup_value(raw_value)) >= 3
    ]

    if not filtered_candidates:
        filtered_candidates = raw_candidates

    best_result = {
        "matched": None,
        "score": 0.0,
        "raw": filtered_candidates[0] if filtered_candidates else "",
        "ambiguous": False
    }

    for raw_value in filtered_candidates:
        result = resolve_best_match(raw_value, candidates, alias_builder, alias_context=alias_context)
        if result["score"] > best_result["score"]:
            best_result = result

    return best_result


def extract_panel_data(image, side):
    if side == "left":
        panel = crop_image(image, 0.02, 0.00, 0.49, 0.95)
        placing = 1
    else:
        panel = crop_image(image, 0.51, 0.00, 0.98, 0.95)
        placing = 2

    character_candidates = collect_ocr_candidates(panel, [
        (0.02, 0.00, 0.55, 0.12, 3.6, (130, 190), (7,)),
        (0.00, 0.00, 0.62, 0.15, 3.6, (130,), (7,)),
    ], include_invert=False)
    tag_candidates = collect_ocr_candidates(panel, [
        (0.13, 0.10, 0.60, 0.20, 3.8, (130, 190), (7,)),
        (0.08, 0.09, 0.68, 0.22, 3.8, (130,), (6,)),
    ], include_invert=True)

    return {
        "tag": tag_candidates[0] if tag_candidates else "",
        "character": character_candidates[0] if character_candidates else "",
        "tag_candidates": tag_candidates,
        "character_candidates": character_candidates,
        "placing": placing,
    }


def enrich_panel_data(image, side, panel_data):
    if side == "left":
        panel = crop_image(image, 0.02, 0.00, 0.49, 0.95)
    else:
        panel = crop_image(image, 0.51, 0.00, 0.98, 0.95)

    extra_character_candidates = collect_ocr_candidates(panel, [
        (0.02, 0.00, 0.55, 0.12, 4.0, (100, 130, 160, 190), (7, 6)),
        (0.00, 0.00, 0.62, 0.15, 4.0, (100, 130, 160, 190), (7, 6)),
    ], include_invert=False)
    extra_tag_candidates = collect_ocr_candidates(panel, [
        (0.13, 0.10, 0.60, 0.20, 4.0, (100, 130, 160, 190, 220), (7, 6)),
        (0.08, 0.09, 0.68, 0.22, 4.0, (100, 130, 160, 190, 220), (7, 6)),
    ], include_invert=True)

    panel_data["character_candidates"] = merge_unique_candidates(
        panel_data.get("character_candidates", []),
        extra_character_candidates
    )
    panel_data["tag_candidates"] = merge_unique_candidates(
        panel_data.get("tag_candidates", []),
        extra_tag_candidates
    )
    return panel_data


def scan_match_image_locally(image_bytes, player_names, player_tag_map):
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise ValueError("The uploaded image could not be read.") from exc

    image = downscale_for_ocr(image)

    entrants = [
        extract_panel_data(image, "left"),
        extract_panel_data(image, "right"),
    ]

    resolved_entries = []
    warnings = []
    normalized_tag_map = {
        normalize_lookup_value(tag): player
        for tag, player in player_tag_map.items()
        if tag and player
    }

    def resolve_entrant(entrant):
        tag_candidates = entrant.get("tag_candidates") or ([entrant.get("tag")] if entrant.get("tag") else [])
        character_candidates = entrant.get("character_candidates") or ([entrant.get("character")] if entrant.get("character") else [])
        direct_player_match = None

        for candidate_tag in tag_candidates:
            normalized_tag = normalize_lookup_value(candidate_tag)
            exact_player = normalized_tag_map.get(normalized_tag)
            if exact_player:
                direct_player_match = {
                    "matched": exact_player,
                    "score": 1.0,
                    "raw": candidate_tag,
                    "ambiguous": False
                }
                break

        if direct_player_match is None:
            direct_player_match = resolve_direct_alias_match(
                tag_candidates,
                player_names,
                build_player_aliases,
                alias_context=player_tag_map
            )

        if direct_player_match is not None:
            player_match = direct_player_match
        else:
            player_match = resolve_best_match_from_candidates(
                tag_candidates,
                player_names,
                build_player_aliases,
                alias_context=player_tag_map
            )

        direct_character_match = resolve_direct_alias_match(
            character_candidates,
            CHARACTERS,
            build_character_aliases
        )

        if direct_character_match is not None:
            character_match = direct_character_match
        else:
            character_match = resolve_best_match_from_candidates(
                character_candidates,
                CHARACTERS,
                build_character_aliases
            )

        return player_match, character_match

    for index, entrant in enumerate(entrants):
        player_match, character_match = resolve_entrant(entrant)

        if (
            not player_match["matched"]
            or not character_match["matched"]
            or player_match["score"] < 0.9
            or character_match["score"] < 0.9
        ):
            side = "left" if index == 0 else "right"
            entrant = enrich_panel_data(image, side, entrant)
            entrants[index] = entrant
            player_match, character_match = resolve_entrant(entrant)

        if not player_match["matched"]:
            warnings.append(f"Could not match tag '{entrant.get('tag', '')}' to a player.")
        elif player_match["ambiguous"]:
            warnings.append(
                f"Tag '{entrant.get('tag', '')}' was matched to '{player_match['matched']}' with low confidence."
            )

        if not character_match["matched"]:
            warnings.append(f"Could not match character '{entrant.get('character', '')}' to the roster.")
        elif character_match["ambiguous"]:
            warnings.append(
                f"Character '{entrant.get('character', '')}' was matched to '{character_match['matched']}' with low confidence."
            )

        resolved_entries.append({
            "parsed_tag": player_match["raw"],
            "parsed_character": character_match["raw"],
            "placing": entrant.get("placing", 0),
            "player": player_match["matched"],
            "player_score": player_match["score"],
            "character": character_match["matched"],
            "character_score": character_match["score"]
        })

    resolved_entries.sort(key=lambda entry: (entry["placing"] or 99, entry["parsed_tag"]))

    placings = [entry["placing"] for entry in resolved_entries]
    if sorted(placings) != [1, 2]:
        raise ValueError("The image did not provide clear 1st and 2nd placings.")

    if any(not entry["player"] or not entry["character"] for entry in resolved_entries):
        raise ValueError("The image parsed, but at least one player or character could not be matched.")

    winner_entry = next(entry for entry in resolved_entries if entry["placing"] == 1)
    loser_entry = next(entry for entry in resolved_entries if entry["placing"] == 2)

    min_confidence = min(
        winner_entry["player_score"],
        winner_entry["character_score"],
        loser_entry["player_score"],
        loser_entry["character_score"]
    )

    return {
        "player1": winner_entry["player"],
        "p1_character": winner_entry["character"],
        "player2": loser_entry["player"],
        "p2_character": loser_entry["character"],
        "winner": "p1",
        "three_stock": False,
        "confidence": round(min_confidence, 3),
        "notes": "",
        "warnings": warnings,
        "summary": (
            f"{winner_entry['player']} ({winner_entry['character']}) beat "
            f"{loser_entry['player']} ({loser_entry['character']})"
        ),
        "resolved_entries": resolved_entries
    }




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
            if m.get("type") == "elo_adjustment":
                continue
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
    """Returns total global ELO offset (sum of character deviations from 1000) plus any manual bonus."""
    if player_name not in players_data:
        return 0
    player_data = players_data[player_name]
    char_total = sum(
        (elo - 1000)
        for char, elo in player_data.items()
        if char in CHARACTERS and isinstance(elo, (int, float))
    )
    bonus = player_data.get("_elo_bonus", 0)
    return char_total + (int(bonus) if isinstance(bonus, (int, float)) else 0)



@app.route("/add_match", methods=["GET", "POST"])
@requires_auth
def add_match():
    if request.method == "GET":
        return redirect(url_for("matches"))

    p1 = request.form["player1"]
    c1 = canonicalize_character_name(request.form["p1_character"])
    p2 = request.form["player2"]
    c2 = canonicalize_character_name(request.form["p2_character"])
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

    if not (c1 == "Random" and c2 == "Random"):
        change1 = apply_random_modifier(c1, change1)
        change2 = apply_random_modifier(c2, change2)
    new1 = old1 + change1
    new2 = old2 + change2






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


@app.route("/api/scan-match-image", methods=["POST"])
@requires_auth
def scan_match_image():
    image = request.files.get("image")
    if not image or not image.filename:
        return {"error": "No image was uploaded."}, 400

    image_bytes = image.read()

    if not image_bytes:
        return {"error": "The uploaded image was empty."}, 400

    if len(image_bytes) > 10 * 1024 * 1024:
        return {"error": "Image is too large. Keep it under 10 MB."}, 400

    player_names = sorted(load_players().keys())
    player_tag_map = load_player_tags()

    try:
        match = scan_match_image_locally(image_bytes, player_names, player_tag_map)
    except ValueError as exc:
        return {"error": str(exc)}, 422
    except RuntimeError as exc:
        return {"error": str(exc)}, 503
    except Exception as exc:
        print("Scan failure:", exc)
        return {"error": "The scan failed unexpectedly."}, 500

    return {"match": match}




@app.route("/admin")
@requires_admin_panel_auth
def admin_panel():
    seasons_data = load_seasons()
    return render_template(
        "admin.html",
        queue_length=len(push_queue),
        pushing_status="Running" if is_pushing else "Idle",
        push_log=push_log,
        pull_log=pull_log,
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



@app.route("/add_elo_adjustment", methods=["POST"])
@requires_auth
def add_elo_adjustment():
    player = request.form.get("player", "").strip()
    amount_str = request.form.get("amount", "").strip()
    note = request.form.get("note", "").strip()

    if not player or not amount_str or not note:
        return "Missing required fields.", 400

    try:
        amount = int(amount_str)
    except ValueError:
        return "Amount must be an integer.", 400

    data = load_players()
    if player not in data:
        return f"Player '{player}' not found.", 404

    current_bonus = data[player].get("_elo_bonus", 0)
    if not isinstance(current_bonus, (int, float)):
        current_bonus = 0
    data[player]["_elo_bonus"] = int(current_bonus) + amount
    save_players(data)

    new_global = compute_global_elo(player, data)

    log = load_match_log()
    log.append({
        "type": "elo_adjustment",
        "timestamp": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M %p"),
        "player": player,
        "amount": amount,
        "note": note,
        "new_global": new_global
    })
    save_match_log(log)

    queue_push("Auto-update from ELO adjustment")
    return redirect(url_for("matches"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
