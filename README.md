# Telegram Message Forwarder

A robust Python-based Telegram message forwarding system with advanced channel resolution, media replacement, and intelligent filtering capabilities.

## Features

- **Bypass Forwarding Restrictions**: Forward messages from channels where forwarding is disabled
- **Custom Media Replacement**: Replace captioned images with custom replacement images
- **Intelligent Text Filtering**: Remove unwanted content like registration messages and promotional text
- **URL Removal**: Clean up links hidden behind markdown-formatted text
- **24/7 Operation**: Designed for continuous operation via Render cloud platform

## Deployment Options

### 1. Deploy on Render Cloud (Recommended)

The easiest way to run the forwarder 24/7 is to deploy it on Render:

1. **Create a Render Account**: Sign up at [render.com](https://render.com/)

2. **Fork this Repository**: Create your own copy on GitHub

3. **Create a New Web Service on Render**:
   - Connect your GitHub account to Render
   - Select your forked repository
   - Use the following settings:
     - **Environment**: Python
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `python main.py`

4. **Configure Environment Variables**:
   - `API_ID`: Your Telegram API ID
   - `API_HASH`: Your Telegram API hash
   - `SOURCE_CHANNEL`: Source channel username/ID
   - `DESTINATION_CHANNEL`: Destination channel username/ID
   - `SESSION_STRING`: (Optional) Your session string if you have one
   - `TEXT_FILTERS`: (Optional) Comma-separated list of text filters

5. **Deploy**:
   - Click "Create Web Service"
   - Render will build and deploy your application
   - On first run, you may need to authenticate through the logs

### 2. Run on Termux (Android)

To run on a mobile device using Termux:

1. Install Termux from F-Droid (recommended) or Google Play Store
2. Open Termux and run:
   ```bash
   pkg update && pkg upgrade
   pkg install python git
   git clone <repository-url>
   cd telegram-forwarder
   pip install -r requirements.txt
   python main.py
   ```

3. Follow on-screen instructions to authenticate

## Configuration

You can configure the forwarder in three ways:

1. **Environment Variables**: Set the required variables in your environment
2. **Web Interface**: Access the web interface at `http://<your-app-url>:5000`
3. **Config File**: Edit the `config.json` file directly

### Required Configuration

- **API ID & Hash**: Get from [my.telegram.org](https://my.telegram.org/)
- **Source Channel**: Username or ID of the channel to forward from
- **Destination Channel**: Username or ID of the channel to forward to

### Optional Configuration

- **Text Filters**: Words or patterns to remove from messages
- **Rate Limit**: Delay between forwarded messages (default: 3 seconds)
- **Media Replacement**: Enable/disable replacing images with captions

## Authentication

The first time you run the forwarder, you'll need to authenticate with Telegram:

1. Enter your phone number (with country code)
2. Enter the verification code sent to your Telegram account
3. If you have Two-Factor Authentication, enter your password

After authentication, the session will be saved for future use.

## Troubleshooting

### Common Issues

- **Connection Errors**: Check your internet connection
- **Authentication Failed**: Verify your API ID and hash
- **Channel Not Found**: Ensure you have the correct channel username/ID
- **Permission Denied**: Make sure your account has access to both channels

For more help, check the logs on Render or in the `forwarder.log` file.

## License

This project is licensed under the MIT License - see the LICENSE file for details.