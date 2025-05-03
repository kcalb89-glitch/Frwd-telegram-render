"""
Configuration module for the Telegram Message Forwarder
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

class Config:
    """Configuration class for the Telegram Message Forwarder"""
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.api_id = None
        self.api_hash = None
        self.source_channel = None
        self.destination_channel = None
        self.session_string = None
        self.text_filters = []
        self.replacement_image_path = 'replacement_image.png'  # Using PNG image for better display in Telegram
        self.rate_limit_delay = 3  # Seconds between messages to avoid flooding
        self.always_replace_media = False  # Only replace media with captions or text
        self.forward_all_messages = True  # Whether to forward all message types
        self.replace_captioned_only = True  # Only replace images that have captions
        
        # Load configuration from environment variables or config file
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment variables or config file"""
        # Try to load from environment variables first
        # Support both with and without TELEGRAM_ prefix for compatibility with Render
        self.api_id = os.getenv('TELEGRAM_API_ID') or os.getenv('API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH') or os.getenv('API_HASH')
        self.source_channel = os.getenv('SOURCE_CHANNEL')
        self.destination_channel = os.getenv('DESTINATION_CHANNEL')
        self.session_string = os.getenv('SESSION_STRING')
        
        # If text filters are in env var, parse them
        text_filters_env = os.getenv('TEXT_FILTERS')
        if text_filters_env:
            try:
                self.text_filters = json.loads(text_filters_env)
            except json.JSONDecodeError:
                self.text_filters = text_filters_env.split(',')
        
        # If env vars are not set, try to load from config file
        if not all([self.api_id, self.api_hash, self.source_channel, self.destination_channel]):
            try:
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r') as f:
                        config_data = json.load(f)
                        
                    self.api_id = config_data.get('api_id', self.api_id)
                    self.api_hash = config_data.get('api_hash', self.api_hash)
                    self.source_channel = config_data.get('source_channel', self.source_channel)
                    self.destination_channel = config_data.get('destination_channel', self.destination_channel)
                    self.session_string = config_data.get('session_string', self.session_string)
                    self.text_filters = config_data.get('text_filters', self.text_filters)
                    self.replacement_image_path = config_data.get('replacement_image_path', self.replacement_image_path)
                    self.rate_limit_delay = config_data.get('rate_limit_delay', self.rate_limit_delay)
                    self.always_replace_media = config_data.get('always_replace_media', self.always_replace_media)
                    self.forward_all_messages = config_data.get('forward_all_messages', self.forward_all_messages)
            except Exception as e:
                logger.error(f"Error loading config file: {str(e)}")
    
    def save(self):
        """Save the current configuration to the config file"""
        config_data = {
            'api_id': self.api_id,
            'api_hash': self.api_hash,
            'source_channel': self.source_channel,
            'destination_channel': self.destination_channel,
            'session_string': self.session_string,
            'text_filters': self.text_filters,
            'replacement_image_path': self.replacement_image_path,
            'rate_limit_delay': self.rate_limit_delay,
            'always_replace_media': self.always_replace_media,
            'forward_all_messages': self.forward_all_messages
        }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=4)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving config file: {str(e)}")
    
    def is_valid(self):
        """Check if the configuration is valid"""
        required_fields = [
            ('api_id', self.api_id),
            ('api_hash', self.api_hash),
            ('source_channel', self.source_channel),
            ('destination_channel', self.destination_channel)
        ]
        
        for field_name, field_value in required_fields:
            if not field_value:
                logger.error(f"Missing required configuration: {field_name}")
                return False
        
        return True
    
    def setup_interactive(self):
        """Setup configuration interactively"""
        print("=== Telegram Message Forwarder Configuration ===")
        
        self.api_id = input(f"Enter API ID ({self.api_id or 'not set'}): ") or self.api_id
        self.api_hash = input(f"Enter API Hash ({self.api_hash or 'not set'}): ") or self.api_hash
        self.source_channel = input(f"Enter Source Channel Username/ID ({self.source_channel or 'not set'}): ") or self.source_channel
        self.destination_channel = input(f"Enter Destination Channel Username/ID ({self.destination_channel or 'not set'}): ") or self.destination_channel
        
        # Handle text filters
        filters_input = input(f"Enter Text Filters (comma-separated) ({','.join(self.text_filters) if self.text_filters else 'not set'}): ")
        if filters_input:
            self.text_filters = [f.strip() for f in filters_input.split(',')]
            
        # Save the configuration
        self.save()
        print("Configuration saved successfully!")
