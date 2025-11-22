import json
import os

# ----------------------------------------
# SETTINGS — MUST MATCH YOUR FLASK APP
# ----------------------------------------

BASE_WIN = 30
BASE_LOSS = 15

def combined_value(char_rating, global_rating):
    return char_rating * 0.7 + global_rating * 0.3

def expected_score(my_combined, opp_combined):
    return 1 / (1 + 10 ** ((opp_combined - my_combined) / 400))

def calculate_elo_custom(p1_char, p2_char, p1_global, p2_global, winner):
    c1 = combined_value(p1_char, p1_global)
    c2 = combined_value(p2_char, p2_global)

    exp_p1 = expected_score(c1, c2)
    exp_p2 = 1 - exp_p1

    expected = exp_p1 if winner == "p1" else exp_p2

    winner_mult = 1 + 1.2 * (0.5 - expected)
    loser_mult  = 1.2 + 0.8 * (0.5 - expected)

    gain = round(BASE_WIN  * winner_mult)
    loss = round(BASE_LOSS * loser_mult)

    if winner == "p1":
        new_p1 = p1_char + gain
        new_p2 = p2_char - loss
    else:
        new_p1 = p1_char - loss
        new_p2 = p2_char + gain

    return max(1000, new_p1), max(1000, new_p2)


# ----------------------------------------
# GLOBAL ELO HELPER
# ----------------------------------------

def compute_global_elo(player, data):
    if player not in data:
        return 0
    return sum(r - 1000 for r in data[player].values())


# ----------------------------------------
# MAIN RECOMPUTE FUNCTION
# ----------------------------------------

def recompute_all():
    if not os.path.exists("match_log.json"):
        raise FileNotFoundError("match_log.json not found!")

    with open("match_log.json", "r") as f:
        match_log = json.load(f)

    # Completely reset players
    players = {}

    new_log = []

    for entry in match_log:
        p1 = entry["p1"]
        p2 = entry["p2"]
        c1 = entry["c1"]
        c2 = entry["c2"]
        winner = entry["winner"]
        three_stock = entry.get("three_stock", False)

        # Ensure structure
        players.setdefault(p1, {})
        players.setdefault(p2, {})
        players[p1].setdefault(c1, 1000)
        players[p2].setdefault(c2, 1000)

        old1 = players[p1][c1]
        old2 = players[p2][c2]

        # Globals before updating
        p1_global = compute_global_elo(p1, players)
        p2_global = compute_global_elo(p2, players)

        # Base new ratings
        new1, new2 = calculate_elo_custom(
            old1, old2, p1_global, p2_global, winner
        )

        change1 = new1 - old1
        change2 = new2 - old2

        # Determine winner/loser global
        if winner == "p1":
            winner_global = compute_global_elo(p1, players)
            loser_global  = compute_global_elo(p2, players)
        else:
            winner_global = compute_global_elo(p2, players)
            loser_global  = compute_global_elo(p1, players)

        # 3-stock multiplier
        if three_stock and winner_global < loser_global:
            change1 *= 2
            change2 *= 2

            if winner == "p1":
                new1 = old1 + change1
                new2 = old2 - change2
            else:
                new1 = old1 - change1
                new2 = old2 + change2

            new1 = max(1000, round(new1))
            new2 = max(1000, round(new2))

        # Record new values
        players[p1][c1] = new1
        players[p2][c2] = new2

        new_log.append({
            "timestamp": entry.get("timestamp") or entry.get("date") or "",
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

        print(f"{p1} ({c1}) vs {p2} ({c2}) → winner {winner}")
        print(f"    New ratings: {new1} / {new2}")

    # Write updated character state
    with open("characters.json", "w") as f:
        json.dump(players, f, indent=4)

    # Replace the real match log
    with open("match_log.json", "w") as f:
        json.dump(new_log, f, indent=4)

    print("\n✔ RECOMPUTE COMPLETE")
    print("✔ characters.json updated")
    print("✔ match_log.json updated with new diffs\n")


if __name__ == "__main__":
    recompute_all()
