#!/usr/bin/env python3
"""
Web interface for the Telegram Message Forwarder
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import asyncio
import threading

# Fix for werkzeug url_quote import on different versions
try:
    # For newer Werkzeug versions
    from werkzeug.urls import url_quote
except ImportError:
    try:
        # For older Werkzeug versions
        from werkzeug.utils import url_quote
    except ImportError:
        # Fallback implementation if neither is available
        import urllib.parse
        def url_quote(string, charset='utf-8'):
            return urllib.parse.quote(string)

from config import Config
from filter_manager import TextFilterManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
# Get port from environment for Render compatibility
port = int(os.environ.get("PORT", 5000))
# Use SESSION_SECRET or generate a secure random key
app.secret_key = os.environ.get("SESSION_SECRET", os.urandom(24).hex())

# Initialize configuration
config = Config()
filter_manager = TextFilterManager(config.text_filters)

# Import the message tracker
from db_handler import MessageTracker

# Global variables for bot control
forwarder_thread = None
forwarder_running = False
client = None
tracker = MessageTracker()

def start_forwarder_thread():
    """Start the forwarder in a separate thread"""
    global forwarder_thread, forwarder_running
    
    if forwarder_thread and forwarder_thread.is_alive():
        logger.warning("Forwarder is already running")
        return False
    
    forwarder_thread = threading.Thread(target=run_forwarder)
    forwarder_thread.daemon = True
    forwarder_thread.start()
    forwarder_running = True
    logger.info("Forwarder thread started")
    return True

def run_forwarder():
    """Run the forwarder asynchronously"""
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    from forwarder import TelegramForwarder
    
    global client, forwarder_running
    
    # Create and run an event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Initialize the Telegram client with in-memory session to avoid permission issues
        if config.session_string:
            client = TelegramClient(StringSession(config.session_string), 
                                 config.api_id, 
                                 config.api_hash)
        else:
            # Use StringSession with empty string to create in-memory session
            client = TelegramClient(StringSession(""), 
                                 config.api_id, 
                                 config.api_hash)

        logger.info("Connecting to Telegram...")
        
        # Define an async helper function
        async def setup_and_start():
            # Start the client
            await client.start()
            
            # Save session string for future use
            if not config.session_string:
                config.session_string = client.session.save()
                config.save()
                logger.info("Session string saved for future use")
                
            # Initialize the forwarder with the tracker
            forwarder = TelegramForwarder(client, config, tracker=tracker)
            
            # Start forwarding messages
            await forwarder.start_forwarding()
            
            logger.info("Forwarder setup complete")
            
        # Run the async setup function
        loop.run_until_complete(setup_and_start())
        
        # Keep the loop running
        logger.info("Forwarder is now running")
        loop.run_forever()
        
    except Exception as e:
        logger.error(f"An error occurred in forwarder thread: {str(e)}", exc_info=True)
        forwarder_running = False
    finally:
        if client and client.is_connected():
            # Properly handle the disconnect coroutine
            async def disconnect_client():
                await client.disconnect()
            
            try:
                loop.run_until_complete(disconnect_client())
                logger.info("Disconnected from Telegram")
            except Exception as e:
                logger.error(f"Error during disconnect: {str(e)}")
        loop.close()
        forwarder_running = False

def stop_forwarder():
    """Stop the forwarder thread"""
    global forwarder_running, client
    
    if not forwarder_running:
        logger.warning("Forwarder is not running")
        return False
    
    forwarder_running = False
    
    # Disconnect the client if it exists
    if client:
        logger.info("Disconnecting from Telegram...")
        # Create a new event loop to disconnect
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Properly handle the disconnect coroutine
            async def disconnect_client():
                await client.disconnect()
            
            loop.run_until_complete(disconnect_client())
        except Exception as e:
            logger.error(f"Error disconnecting client: {str(e)}")
        finally:
            loop.close()
    
    logger.info("Forwarder stopped")
    return True

@app.route('/')
def index():
    """Main page - configuration dashboard"""
    global forwarder_running
    
    return render_template('index.html', 
                          config=config,
                          filters=config.text_filters,
                          is_running=forwarder_running)

@app.route('/setup', methods=['POST'])
def setup():
    """Save configuration settings"""
    config.api_id = request.form.get('api_id')
    config.api_hash = request.form.get('api_hash')
    config.source_channel = request.form.get('source_channel')
    config.destination_channel = request.form.get('destination_channel')
    
    # Get and parse text filters
    filters_input = request.form.get('text_filters', '')
    if filters_input:
        config.text_filters = [f.strip() for f in filters_input.split(',')]
    else:
        config.text_filters = []
    
    # Rate limit delay
    try:
        config.rate_limit_delay = int(request.form.get('rate_limit_delay', 3))
    except ValueError:
        config.rate_limit_delay = 3
        
    # Save configuration
    config.save()
    filter_manager.clear_filters()
    filter_manager.add_filters(config.text_filters)
    
    flash('Configuration saved successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/start', methods=['POST'])
def start_forwarder():
    """Start the forwarder"""
    global forwarder_running, tracker
    
    if not config.is_valid():
        flash('Invalid configuration. Please check your settings.', 'danger')
        return redirect(url_for('index'))
    
    if forwarder_running:
        flash('Forwarder is already running.', 'warning')
        return redirect(url_for('index'))
    
    # Reset the message tracking database when starting
    # This ensures we process all messages in the source channel
    try:
        tracker.reset_database()
        logger.info("Message tracking database reset on forwarder start")
    except Exception as e:
        logger.error(f"Failed to reset database on start: {str(e)}")
    
    if start_forwarder_thread():
        flash('Forwarder started successfully! Message database has been reset to process all messages.', 'success')
    else:
        flash('Failed to start forwarder.', 'danger')
    
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop_forwarder_route():
    """Stop the forwarder"""
    global forwarder_running
    
    if not forwarder_running:
        flash('Forwarder is not running.', 'warning')
        return redirect(url_for('index'))
    
    if stop_forwarder():
        flash('Forwarder stopped successfully!', 'success')
    else:
        flash('Failed to stop forwarder.', 'danger')
    
    return redirect(url_for('index'))

@app.route('/status')
def status():
    """Get the forwarder status - also serves as a health check endpoint for Render"""
    global forwarder_running, client
    
    auth_status = 'not_started'
    if forwarder_running:
        if client and client.is_connected():
            auth_status = 'authenticated'
        elif 'auth_step' in session:
            auth_status = session['auth_step']
        else:
            auth_status = 'connecting'
    
    status_response = {
        'running': forwarder_running,
        'config_valid': config.is_valid(),
        'auth_status': auth_status,
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    }
    
    return jsonify(status_response)

@app.route('/reset-db', methods=['POST'])
def reset_database():
    """Reset the message tracking database"""
    global tracker
    
    if tracker.reset_database():
        flash('Message tracking database has been reset successfully.', 'success')
    else:
        flash('Failed to reset message tracking database.', 'danger')
    
    return redirect(url_for('index'))

@app.route('/auth/phone', methods=['POST'])
def auth_phone():
    """Provide phone number for authentication"""
    phone = request.form.get('phone')
    if not phone:
        return jsonify({'status': 'error', 'message': 'Phone number is required'}), 400
    
    session['phone'] = phone
    session['auth_step'] = 'waiting_code'
    
    return jsonify({'status': 'success', 'message': 'Phone number received'})

@app.route('/auth/code', methods=['POST'])
def auth_code():
    """Provide verification code for authentication"""
    code = request.form.get('code')
    if not code:
        return jsonify({'status': 'error', 'message': 'Verification code is required'}), 400
    
    session['code'] = code
    session['auth_step'] = 'waiting_password'
    
    return jsonify({'status': 'success', 'message': 'Verification code received'})

@app.route('/auth/password', methods=['POST'])
def auth_password():
    """Provide 2FA password if needed"""
    password = request.form.get('password')
    if not password:
        return jsonify({'status': 'error', 'message': 'Password is required'}), 400
    
    session['password'] = password
    session['auth_step'] = 'authenticating'
    
    return jsonify({'status': 'success', 'message': 'Password received'})

if __name__ == '__main__':
    # Use port from environment variable for Render compatibility
    app.run(host='0.0.0.0', port=port, debug=True)