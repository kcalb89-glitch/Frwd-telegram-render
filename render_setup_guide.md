# Render Deployment Guide

This guide provides step-by-step instructions for deploying the Telegram Message Forwarder on Render.com for 24/7 operation.

## Prerequisites

Before you begin, make sure you have:

1. A GitHub account
2. A Render.com account (sign up at [render.com](https://render.com/))
3. Your Telegram API credentials:
   - API ID
   - API Hash
   (Get these from [my.telegram.org](https://my.telegram.org/))
4. Source and destination channel information

## Step 1: Prepare Your Repository

1. Fork this repository to your GitHub account
2. Make sure the repository contains:
   - All Python files (`main.py`, `app.py`, `forwarder.py`, etc.)
   - `requirements.txt` with all dependencies
   - `Procfile` for Render
   - `render.yaml` configuration

## Step 2: Connect to Render

1. Log in to your Render dashboard
2. Click "New" and select "Web Service"
3. Connect your GitHub account if you haven't already
4. Select the forked repository

## Step 3: Configure the Web Service

Configure your Render web service with these settings:

1. **Name**: Choose a name for your service (e.g., "telegram-forwarder")
2. **Environment**: Python
3. **Region**: Choose a region close to you
4. **Branch**: main (or your preferred branch)
5. **Build Command**: `pip install -r requirements.txt`
6. **Start Command**: `python main.py`

## Step 4: Set Environment Variables

Add the following environment variables:

| Variable | Value | Description |
|----------|-------|-------------|
| `API_ID` | Your API ID | Telegram API ID from my.telegram.org |
| `API_HASH` | Your API Hash | Telegram API Hash from my.telegram.org |
| `SOURCE_CHANNEL` | @username or -100... | Channel to forward from |
| `DESTINATION_CHANNEL` | @username or -100... | Channel to forward to |
| `SESSION_STRING` | (Optional) | Session string if you already have one |
| `TEXT_FILTERS` | (Optional) | Comma-separated filters |
| `PORT` | 10000 | Port for the web interface |

## Step 5: Deploy

1. Click "Create Web Service"
2. Render will build and deploy your application
3. Once deployed, check the logs for any errors or authentication prompts

## Step 6: First-Time Authentication

The first time you run the forwarder, you'll need to authenticate:

1. Watch the logs in your Render dashboard
2. When prompted, enter your phone number in the international format (e.g., +1234567890)
3. Enter the verification code sent to your Telegram
4. If you have 2FA enabled, enter your password

After successful authentication, the session string will be saved and reused for future deployments.

## Step 7: Verify Operation

1. Check the logs to ensure the forwarder is running correctly
2. Verify that messages are being forwarded from the source to the destination channel
3. If you need to adjust any settings, update the environment variables and redeploy

## Troubleshooting

### Authentication Issues

If you're having trouble with authentication:

1. Use the web interface at `https://your-app-name.onrender.com` to set up authentication
2. Or, run the forwarder locally first to generate a session string, then add it to Render as the `SESSION_STRING` environment variable

### Connection Issues

If the forwarder can't connect to Telegram:

1. Verify your API ID and API Hash
2. Check if your IP might be blocked by Telegram
3. Ensure your account isn't limited or restricted

### Deployment Issues

If deployment fails:

1. Check the build logs for errors
2. Verify your `requirements.txt` includes all dependencies
3. Make sure your start command matches your file structure