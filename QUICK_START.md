# 🚀 Quick Start - Deploy to Render

## Step 1: Restart PowerShell ⚡
**IMPORTANT:** Close this PowerShell window and open a NEW one!

## Step 2: Run These Commands 📝

```powershell
# Navigate to project
cd c:\Users\Student\Desktop\restauran-main

# Configure Git (first time only)
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Initialize repository
git init
git add .
git commit -m "Initial commit with keep-alive system"
git branch -M main
```

## Step 3: Deploy to Render 🌐

### Option A: Direct Deployment (Easiest)
1. Go to https://dashboard.render.com/
2. Click "New +" → "Web Service"
3. Choose "Public Git repository"
4. Upload your code or connect GitHub
5. Set these values:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

### Option B: Via GitHub
1. Create repo at https://github.com/new
2. Run:
```powershell
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```
3. Connect Render to GitHub repo

## Step 4: Set Environment Variables on Render ⚙️

**CRITICAL - Add these in Render Dashboard:**

```
RENDER_EXTERNAL_URL = https://your-app-name.onrender.com
SECRET_KEY = your-secret-key-here
OPENAI_API_KEY = your-openai-key-here
MAIL_USERNAME = your-email@gmail.com
MAIL_PASSWORD = your-email-app-password
```

> ⚠️ **IMPORTANT:** `RENDER_EXTERNAL_URL` is required for the keep-alive system!

## Step 5: Verify It's Working ✅

1. Visit: `https://your-app-name.onrender.com`
2. Check health: `https://your-app-name.onrender.com/health`
3. View Render logs for: `[Keep-Alive] Background worker started`

---

## 📚 Need More Help?

- Full guide: See `GIT_SETUP_GUIDE.md`
- Keep-alive info: See `KEEP_ALIVE_SETUP.md`

## 🎉 That's It!

Your site will now stay active 24/7 on Render!
