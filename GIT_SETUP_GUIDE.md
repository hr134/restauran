# Git Setup and Deployment Guide

## ✅ Git Installation Complete!

Git has been successfully installed on your system.

## 🔄 Next Steps

### Step 1: Restart Your Terminal
**IMPORTANT:** Close your current PowerShell window and open a new one for Git to work properly.

### Step 2: Configure Git (First Time Only)
Open a new PowerShell window and run these commands:

```powershell
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Replace with your actual name and email.

### Step 3: Initialize Git Repository
Navigate to your project folder and run:

```powershell
cd c:\Users\Student\Desktop\restauran-main

# Initialize Git repository
git init

# Add all files to staging
git add .

# Create initial commit
git commit -m "Initial commit with keep-alive system"

# Rename branch to main
git branch -M main
```

### Step 4: Connect to GitHub/Render

#### Option A: Deploy to Render (Direct)
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Choose "Public Git repository" or connect your GitHub
4. Enter your repository URL
5. Configure:
   - **Name**: your-app-name
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
6. Add Environment Variables:
   - `RENDER_EXTERNAL_URL` = `https://your-app-name.onrender.com`
   - `SECRET_KEY` = (generate a random secret key)
   - `OPENAI_API_KEY` = (your OpenAI API key)
   - `MAIL_USERNAME` = (your email)
   - `MAIL_PASSWORD` = (your email password)
7. Click "Create Web Service"

#### Option B: Push to GitHub First
1. Create a new repository on [GitHub](https://github.com/new)
2. Copy the repository URL
3. Run these commands:

```powershell
# Add GitHub as remote
git remote add origin https://github.com/yourusername/your-repo-name.git

# Push to GitHub
git push -u origin main
```

4. Then connect Render to your GitHub repository

## 📝 Important Files to Check

Before deploying, make sure you have:

### 1. `.gitignore` file
```
__pycache__/
*.pyc
*.pyo
*.db
instance/
.env
venv/
.vscode/
*.log
```

### 2. `requirements.txt`
Make sure all dependencies are listed. Run:
```powershell
pip freeze > requirements.txt
```

### 3. Environment Variables on Render
- `RENDER_EXTERNAL_URL` - **REQUIRED for keep-alive system**
- `SECRET_KEY`
- `OPENAI_API_KEY`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_SERVER` (optional, defaults to smtp.gmail.com)
- `MAIL_PORT` (optional, defaults to 587)

## 🚀 Keep-Alive System

Once deployed with `RENDER_EXTERNAL_URL` set, the keep-alive system will:
- ✅ Start automatically
- ✅ Ping itself every 14 minutes
- ✅ Keep your site active 24/7
- ✅ Log all pings in Render logs

## 🔍 Verify Deployment

1. Visit your site: `https://your-app-name.onrender.com`
2. Check health endpoint: `https://your-app-name.onrender.com/health`
3. Check Render logs for: `[Keep-Alive] Background worker started`

## 🆘 Troubleshooting

### Git not recognized after installation
- Close and reopen PowerShell
- Or restart your computer

### Git commands fail
- Make sure you're in the project directory
- Check if Git is installed: `git --version`

### Keep-Alive not working
- Verify `RENDER_EXTERNAL_URL` is set correctly
- Check Render logs for errors
- Make sure URL matches your actual Render URL

## 📚 Useful Git Commands

```powershell
# Check status
git status

# Add specific files
git add filename.py

# Commit changes
git commit -m "Your commit message"

# Push to remote
git push

# Pull latest changes
git pull

# View commit history
git log --oneline

# Create new branch
git checkout -b feature-name
```

## 🎉 You're All Set!

Your restaurant management system is now ready to deploy with:
- ✅ Git version control
- ✅ Automatic keep-alive system
- ✅ All features working
- ✅ Ready for production

Happy coding! 🚀
