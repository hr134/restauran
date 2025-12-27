# Keep-Alive System for Render

## Overview
This application now includes an automatic keep-alive system that prevents Render from putting your site to sleep after 15 minutes of inactivity.

## How It Works

### Server-Side Keep-Alive (Recommended)
The application includes a background thread that automatically pings itself every 14 minutes to maintain activity.

**Features:**
- ✅ Works even when no users are visiting the site
- ✅ Runs automatically in production
- ✅ No user interaction required
- ✅ Minimal resource usage

**Components:**
1. **Health Check Endpoint** (`/health`) - A lightweight endpoint that responds to ping requests
2. **Background Worker Thread** - Runs in the background and pings the `/health` endpoint every 14 minutes
3. **Smart Activation** - Only runs when deployed on Render (checks for `RENDER_EXTERNAL_URL` environment variable)

## Setup on Render

### Step 1: Set Environment Variable
In your Render dashboard, add the following environment variable:

```
RENDER_EXTERNAL_URL = https://your-app-name.onrender.com
```

Replace `your-app-name.onrender.com` with your actual Render URL.

### Step 2: Deploy
Deploy your application to Render. The keep-alive system will start automatically.

### Step 3: Verify
Check your Render logs. You should see:
```
[Keep-Alive] Background worker started - site will ping itself every 14 minutes
[Keep-Alive] ✓ Ping successful at 2025-12-27 15:05:40
```

## How to Check if It's Working

1. **Check Logs**: Look for `[Keep-Alive]` messages in your Render logs
2. **Visit Health Endpoint**: Go to `https://your-app-name.onrender.com/health` - you should see:
   ```json
   {
     "status": "alive",
     "timestamp": "2025-12-27T15:05:40.123456",
     "message": "Site is active"
   }
   ```

## Technical Details

- **Ping Interval**: 14 minutes (840 seconds)
- **Initial Delay**: 2 minutes after startup
- **Timeout**: 10 seconds per ping request
- **Thread Type**: Daemon thread (automatically stops when app stops)

## Local Development

The keep-alive system **will not run** on your local machine (localhost) unless you manually set the `RENDER_EXTERNAL_URL` environment variable. This is intentional to avoid unnecessary pings during development.

## Troubleshooting

### Keep-Alive Not Working?

1. **Check Environment Variable**: Ensure `RENDER_EXTERNAL_URL` is set correctly in Render
2. **Check Logs**: Look for error messages in the `[Keep-Alive]` logs
3. **Verify URL**: Make sure the URL in `RENDER_EXTERNAL_URL` is accessible

### Site Still Going to Sleep?

- Render's free tier may still sleep after extended periods of inactivity
- Consider upgrading to a paid plan for guaranteed uptime
- Alternatively, use an external service like [UptimeRobot](https://uptimerobot.com/) or [Cron-Job.org](https://cron-job.org/) to ping your site

## Alternative: External Monitoring Services

If you want additional reliability, you can also use external services:

### UptimeRobot (Free)
1. Sign up at https://uptimerobot.com/
2. Create a new monitor
3. Set URL to: `https://your-app-name.onrender.com/health`
4. Set interval to 5 minutes

### Cron-Job.org (Free)
1. Sign up at https://cron-job.org/
2. Create a new cron job
3. Set URL to: `https://your-app-name.onrender.com/health`
4. Set schedule to every 14 minutes

## Notes

- The built-in keep-alive system is sufficient for most use cases
- External services provide redundancy and monitoring
- Both can be used together for maximum reliability
