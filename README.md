# Smash ELO App

A lightweight web app for tracking Super Smash Bros. Ultimate matches using an ELO rating system. Built to be fast, transparent, and easy to extend, the app records matches, updates player ratings, and displays rankings with basic stats and achievements.

This project is designed as a personal tool rather than a commercial platform, prioritizing simplicity, control over data, and hackability.

## Features

- ELO-based ranking system for Smash Ultimate players
- Match logging with automatic rating updates
- Player leaderboard sorted by current ELO
- Individual player pages with match history and stats
- Badge and achievement system
- Lightweight UI with mobile support
- JSON-backed data storage synced to GitHub

## Tech Stack

- Python
- Flask
- HTML / CSS
- JavaScript
- JSON
- GitHub for versioned storage and sync

## How the ELO System Works

Each player starts with a default ELO rating

Winning against higher-rated opponents yields larger gains

Losing to lower-rated opponents results in larger drops

Ratings adjust dynamically based on opponent strength

Optional modifiers support streaks, decay, or custom tuning

The ELO logic lives in a dedicated module, making it easy to tweak formulas without touching the rest of the app.

## Project Structure
smash-elo-app/
│
├── app.py                  # Flask entry point
├── elo.py                  # ELO calculation logic
├── data/
│   ├── players.json        # Player data
│   ├── match_log.json      # Match history
│   └── badges.json         # Badge definitions
│
├── templates/              # Jinja HTML templates
├── static/
│   ├── css/                # Stylesheets
│   ├── js/                 # Frontend logic
│   └── images/             # Icons and badges
│
└── README.md

## Running the App Locally

### Clone the repository:

git clone https://github.com/yourusername/smash-elo-app.git
cd smash-elo-app


### Create and activate a virtual environment:

python3 -m venv venv
source venv/bin/activate


### Install dependencies:

pip install flask


### Run the app:

python app.py

Visit http://127.0.0.1:5000 in your browser.

### Adding Matches

Select the winning and losing player

### Submit the match

ELO updates instantly

Match is written to match_log.json

Leaderboard and player pages update automatically

## Badges and Achievements

Badges are awarded based on conditions such as:

Win streaks

Upsets against higher-rated players

Total matches played

Special milestones

Badge logic is intentionally decoupled so new achievements can be added without rewriting match logic.

## Data Storage Philosophy

All data is stored in plain JSON files to keep things:

Transparent

Version-controlled

Easy to back up

Easy to migrate

GitHub sync ensures match history and ratings remain auditable over time.

## Planned Improvements

ELO decay for inactivity

Match filtering and search

Per-character stats

Exportable stats and CSV downloads

Improved badge visuals and animations

License

This project is for personal and educational use. Modify, extend, and experiment freely.
