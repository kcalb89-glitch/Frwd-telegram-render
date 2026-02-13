#!/usr/bin/env python3
"""
Telegram Message Forwarder - Main Entry Point
This script initializes and runs the Telegram message forwarding system.
"""
import threading
from flask import Flask
import os
import sys
import time
import logging
import asyncio
import argparse
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from config import Config
from forwarder import TelegramForwarder

# Import app from app.py for Gunicorn to work
from app import app

# Configure logging
log_file = os.environ.get('LOG_FILE', 'forwarder.log')
log_level = os.environ.get('LOG_LEVEL', 'INFO')

# Initialize handlers list with stdout always
handlers = [logging.StreamHandler(sys.stdout)]

# Only add file handler if we're not in a read-only environment like Render
try:
    file_handler = logging.FileHandler(log_file)
    # Explicitly add as a Handler type to avoid type checking issues
    handlers.append(file_handler)  # type: ignore
except (IOError, PermissionError) as e:
    # Skip file logging if we can't write to the file
    print(f"Warning: Could not create log file: {str(e)}. Logging to stdout only.")

logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)
logger = logging.getLogger(__name__)
def run_web_server():
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "Bot is running"
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
async def main():
    logger.info("Starting forwarder...")

    """Main function that initializes and runs the forwarder"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Telegram Message Forwarder')
    parser.add_argument('--config', type=str, default='config.json', help='Path to config file')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    logger.info("Starting Telegram message forwarder...")
    
    # Load configuration
    config = Config(args.config)
    if not config.is_valid():
        logger.error("Invalid configuration. Please set up your config file correctly or use the web interface at http://localhost:5000")
        return
    
    # Initialize the Telegram client
    try:
        # Always use StringSession to handle Render's ephemeral filesystem
        # If we have a session string, use it, otherwise create a new in-memory session
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
        await client.start()
     
        # Save session string for future use
        if not config.session_string:
            config.session_string = client.session.save()
            config.save()
            logger.info("Session string saved for future use")
            
        # Initialize the forwarder
        forwarder = TelegramForwarder(client, config)
        
        # Start forwarding messages
        await forwarder.start_forwarding()
        
        # Keep the script running
        logger.info("Forwarder is now running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(3600)  # Keep the script running
      # === Dialogs loading ===
    try:
        logger.info("Check dialogs for cash...")
        dialogs = await client.get_dialogs()
        logger.info(f"✅ Dialogs: {len(dialogs)}")
        
        # Check groop id`s
        dest_id = int(os.environ.get('DESTINATION_CHANNEL'))
        try:
            dest_entity = await client.get_entity(dest_id)
            logger.info(f"✅ Group not found: {getattr(dest_entity, 'title', 'N/A')}")
        except Exception as e:
            logger.error(f"❌ Can not find group with ID {dest_id} even after get_dialogs: {e}")
            # Print all dialogs for testing
            logger.info("Dialogs:")
            for dialog in dialogs:
                logger.info(f"  - {dialog.name} (ID: {dialog.id})")
    except Exception as e:
        logger.error(f"Check dialogs fault: {e}")          
    except KeyboardInterrupt:
        logger.info("Stopping forwarder due to keyboard interrupt...")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
    finally:
        # Handle client variable in a way that satisfies type checking
        if 'client' in locals():
            client_var = locals()['client']
            if hasattr(client_var, 'is_connected') and client_var.is_connected():
                await client_var.disconnect()
                logger.info("Disconnected from Telegram")

if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.critical(f"Critical error: {str(e)}", exc_info=True)
