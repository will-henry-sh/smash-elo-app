# Security Setup Instructions

## Environment Variables Configuration

This application now uses environment variables to store sensitive credentials securely.

### Local Development Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your actual credentials:
   ```
   ADMIN_USER_1=username1:password1
   ADMIN_USER_2=username2:password2
   ADMIN_USER_3=username3:password3
   ADMIN_NAMES=Name1,Name2,Name3
   ```

3. The `.env` file is gitignored and will NOT be committed to version control.

### Production Deployment (Render)

Set the following environment variables in your Render dashboard:

- `ADMIN_USER_1`: `bunnyslave:Letskill666`
- `ADMIN_USER_2`: `todaycowboy:Heisrisen!`
- `ADMIN_USER_3`: `protodong:Icecoffin666`
- `ADMIN_NAMES`: `Will,Colton,Nick R`

### Important Security Notes

- Never commit the `.env` file to git
- Never share your `.env` file publicly
- Change default passwords immediately
- Use strong, unique passwords for each admin account
- Consider implementing more robust authentication (OAuth, JWT) for production use

### Installing Dependencies

```bash
pip install -r requirements.txt
```

This will install `python-dotenv` along with other required packages.
