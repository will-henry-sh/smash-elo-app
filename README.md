# Smash Ultimate ELO Tracker

A lightweight Flask web app for tracking competitive Super Smash Bros. Ultimate ELO ratings between friends. The app calculates character-specific ELO, maintains match history, generates player stat pages, and ranks players using a global ELO system based on performance across all used characters.

## Features

Match Submission Page

Select players from controlled dropdowns (no manual name entry)

Searchable character dropdowns

Auto-filled last-used characters/players

Immediate display of last match results with rating changes

## Leaderboard

Global ELO based on sum of character rating differences from 1000

Ignores unused characters (1000 ELO)

Rankings with gold/silver/bronze highlights for top 3

Character dropdown to view ratings for different mains

Click a player's name to open their stats page

## Player Stats Pages

Character-specific ELO table

Best and worst character

Total matches played

Wins, losses, and win percentage

Match History Logging

Stores all matches in match_log.json

Stores current ELO values in characters.json

## ELO System

Standard ELO formula with rating differential

K-factor = 32

ELO floor at 800 to help newer/less experienced players

## File Structure

app.py
templates/
    index.html
    leaderboard.html
    player_stats.html
static/
    styles.css
characters.json
match_log.json
last_result.json

## Running the App

python3 app.py

http://127.0.0.1:5001

## Resetting Data

To reset ratings and match history, delete:

characters.json

match_log.json

last_result.json

The app will recreate them automatically.
