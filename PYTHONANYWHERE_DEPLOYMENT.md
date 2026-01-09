# PythonAnywhere Deployment Guide

## Step 1: Upload Your Code to PythonAnywhere

### Option A: Upload via Git (Recommended)
1. Push your code to GitHub
2. In PythonAnywhere, open a Bash console
3. Clone your repository:
   ```bash
   git clone https://github.com/yourusername/smash-elo-app.git
   cd smash-elo-app
   ```

### Option B: Upload Files Directly
1. Go to the "Files" tab in PythonAnywhere
2. Upload all your project files

## Step 2: Set Up Virtual Environment

In a PythonAnywhere Bash console:

```bash
cd ~/smash-elo-app  # or wherever you uploaded the code
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 3: Create the .env File

Create a `.env` file in your project directory with your credentials:

```bash
nano .env
```

Add the following content:
```
ADMIN_USER_1=bunnyslave:Letskill666
ADMIN_USER_2=todaycowboy:Heisrisen!
ADMIN_USER_3=protodong:Icecoffin666
ADMIN_NAMES=Will,Colton,Nick R
```

Save with `Ctrl+O`, `Enter`, then exit with `Ctrl+X`.

## Step 4: Configure the Web App

1. Go to the **Web** tab in PythonAnywhere
2. Click **Add a new web app**
3. Choose **Manual configuration** (don't choose Flask wizard)
4. Select **Python 3.9** (or your preferred version)

### Configure the WSGI file:

1. Click on the **WSGI configuration file** link (it will be something like `/var/www/yourusername_pythonanywhere_com_wsgi.py`)
2. **Delete all the default content** and replace with:

```python
import sys
import os

# Add your project directory to the sys.path
project_home = '/home/yourusername/smash-elo-app'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, '.env'))

# Import your Flask app
from app import app as application
```

**Important:** Replace `yourusername` with your actual PythonAnywhere username!

### Set the Virtual Environment Path:

1. In the **Web** tab, find the **Virtualenv** section
2. Enter the path to your virtual environment:
   ```
   /home/yourusername/smash-elo-app/venv
   ```
   (Replace `yourusername` with your actual username)

### Set the Working Directory:

1. In the **Web** tab, find the **Code** section
2. Set **Source code** to:
   ```
   /home/yourusername/smash-elo-app
   ```

## Step 5: Configure Static Files

In the **Web** tab, add static file mappings:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/yourusername/smash-elo-app/static` |

## Step 6: Set Up Data Persistence

Your JSON data files will be stored in your project directory. PythonAnywhere persists these automatically.

## Step 7: Reload the Web App

Click the big green **Reload** button at the top of the Web tab.

## Step 8: Test Your App

Visit: `https://yourusername.pythonanywhere.com`

## Troubleshooting

### View Error Logs
Go to **Web** tab → Click on **Error log** or **Server log** to see any errors.

### Common Issues:

1. **Import errors**: Check that all paths in the WSGI file use your actual username
2. **Module not found**: Make sure virtualenv path is correct and `requirements.txt` was installed
3. **500 errors**: Check the error log for details
4. **Static files not loading**: Verify static file mapping paths are correct

### Updating Your App

When you make changes:

```bash
cd ~/smash-elo-app
git pull  # if using git
source venv/bin/activate
pip install -r requirements.txt  # if dependencies changed
```

Then click **Reload** in the Web tab.

### Git Auto-Push Feature

Note: The automatic git commit/push feature in your app may not work on PythonAnywhere's free tier due to restricted git access. You may need to:
- Manually pull changes periodically, OR
- Comment out the git push functionality in app.py if it causes issues

## Free Tier Limitations

- Your app will sleep after inactivity
- Limited CPU time per day
- No custom domains on free tier
- Git push may be restricted

For a production app with more traffic, consider upgrading to a paid plan.

## Admin Access

Your admin panel will be at:
- `https://yourusername.pythonanywhere.com/admin`

Use the credentials from your `.env` file to log in.
