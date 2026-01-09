# Troubleshooting PythonAnywhere Deployment

## If the app crashes after update:

### Step 1: Check Error Logs
1. Go to **Web** tab in PythonAnywhere
2. Click **Error log** to see what's causing the crash
3. Look for error messages about imports or missing modules

### Step 2: Verify python-dotenv is installed
In a Bash console:
```bash
cd ~/smash-elo-app  # or your project directory
source venv/bin/activate
pip install python-dotenv
```

### Step 3: If Still Crashing - Temporary Fix
The updated code now has **fallback credentials** built-in. Even if the .env file isn't found, the app will use the original hardcoded credentials and display a warning.

### Step 4: Check .env file location
Make sure the `.env` file is in the same directory as `app.py`:
```bash
cd ~/smash-elo-app
ls -la .env
cat .env  # verify contents
```

The `.env` file should contain:
```
ADMIN_USER_1=bunnyslave:Letskill666
ADMIN_USER_2=todaycowboy:Heisrisen!
ADMIN_USER_3=protodong:Icecoffin666
ADMIN_NAMES=Will,Colton,Nick R
```

### Step 5: Check for Syntax Errors
```bash
cd ~/smash-elo-app
python3 -m py_compile app.py
```
If this shows errors, the file upload may have been corrupted.

### Step 6: Reload Web App
After making any changes:
1. Go to **Web** tab
2. Click the green **Reload** button

## Quick Rollback if Needed

If you need to quickly restore the old version:
1. Go to Files tab
2. Open `app.py`
3. Find lines 25-48 (the credential loading section)
4. Replace with the old hardcoded version:

```python
# Admin login credentials
ADMIN_USERS = {
    "bunnyslave": "Letskill666",
    "todaycowboy": "Heisrisen!",
    "protodong": "Icecoffin666"
}
ADMIN_USERNAMES = ["Will", "Colton", "Nick R"]
```

5. Remove the dotenv import (lines 9-13)
6. Reload the web app

## Current Version Benefits

The current code now has:
- **Graceful fallback**: Will use hardcoded credentials if .env isn't found
- **Safe import**: Won't crash if python-dotenv isn't installed
- **Debug output**: Prints how many admin users were loaded
