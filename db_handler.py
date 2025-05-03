"""
Database handler for the Telegram message forwarding system.
Tracks forwarded messages to avoid duplicates.
"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MessageTracker:
    """
    Tracks forwarded messages to avoid duplicates.
    Uses SQLite for storage with fallback to in-memory tracking.
    """
    
    def __init__(self, db_file='forwarded_messages.db'):
        self.db_file = os.environ.get('DB_FILE', db_file)
        self.use_sqlite = True
        self.in_memory_messages = set()  # Fallback if SQLite fails
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize the SQLite database with fallback to in-memory tracking"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS forwarded_messages (
                    message_id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL
                )
            ''')
            
            conn.commit()
            conn.close()
            self.use_sqlite = True
            logger.info(f"Database initialized: {self.db_file}")
        except (sqlite3.OperationalError, IOError, PermissionError) as e:
            self.use_sqlite = False
            logger.warning(f"SQLite database initialization failed: {str(e)}. Using in-memory tracking instead.")
    
    def is_forwarded(self, message_id):
        """Check if a message was already forwarded"""
        # If in-memory tracking is being used due to SQLite failure
        if not self.use_sqlite:
            result = message_id in self.in_memory_messages
            if result:
                logger.info(f"Message {message_id} found in memory as already forwarded")
            else:
                logger.info(f"Message {message_id} is new, not found in memory")
            return result
            
        # Otherwise use SQLite
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute("SELECT 1 FROM forwarded_messages WHERE message_id = ?", (message_id,))
            result = cursor.fetchone() is not None
            
            conn.close()
            
            # Add debug log to see if messages are being detected as already forwarded
            if result:
                logger.info(f"Message {message_id} found in database as already forwarded")
            else:
                logger.info(f"Message {message_id} is new, not found in database")
                
            return result
        except Exception as e:
            # If SQLite fails, switch to in-memory tracking and try again
            logger.error(f"Error checking if message was forwarded: {str(e)}. Switching to in-memory tracking.")
            self.use_sqlite = False
            return message_id in self.in_memory_messages
    
    def mark_as_forwarded(self, message_id):
        """Mark a message as forwarded"""
        # Always update in-memory tracking as backup
        self.in_memory_messages.add(message_id)
        
        # If in-memory tracking is being used due to SQLite failure
        if not self.use_sqlite:
            logger.debug(f"Message {message_id} marked as forwarded in memory")
            return
        
        # Otherwise use SQLite
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Insert the message ID with current timestamp
            cursor.execute(
                "INSERT OR REPLACE INTO forwarded_messages (message_id, timestamp) VALUES (?, ?)",
                (message_id, datetime.now().isoformat())
            )
            
            conn.commit()
            conn.close()
            logger.debug(f"Message {message_id} marked as forwarded in database")
        except Exception as e:
            # If SQLite fails, switch to in-memory tracking
            logger.error(f"Error marking message as forwarded: {str(e)}. Using in-memory tracking only.")
            self.use_sqlite = False
    
    def clear_old_records(self, days=30):
        """Clear old records to prevent the database from growing too large"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM forwarded_messages WHERE timestamp < ?", (cutoff_date,))
            deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if deleted > 0:
                logger.info(f"Cleared {deleted} old message records from database")
        except Exception as e:
            logger.error(f"Error clearing old records: {str(e)}")
            
    def reset_database(self):
        """Reset/clear the entire message tracking database"""
        # Always clear in-memory tracking
        previous_count = len(self.in_memory_messages)
        self.in_memory_messages.clear()
        
        # If we're not using SQLite, just report the memory clear
        if not self.use_sqlite:
            logger.info(f"Reset in-memory message tracking - cleared {previous_count} message records")
            return True
        
        # Otherwise, try to reset the SQLite database too
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Count records before deletion
            cursor.execute("SELECT COUNT(*) FROM forwarded_messages")
            db_count = cursor.fetchone()[0]
            
            # Delete all records
            cursor.execute("DELETE FROM forwarded_messages")
            
            conn.commit()
            conn.close()
            
            total_count = db_count + (0 if previous_count == 0 else previous_count)
            logger.info(f"Reset message tracking - deleted {total_count} message records (DB: {db_count}, Memory: {previous_count})")
            return True
        except Exception as e:
            logger.error(f"Error resetting database: {str(e)}. But in-memory tracking was reset.")
            self.use_sqlite = False
            return True  # Still return true since in-memory was reset successfully


class SimpleMessageTracker:
    """
    A simple in-memory message tracker with JSON file persistence.
    Can be used as a fallback if SQLite is not available.
    """
    
    def __init__(self, storage_file='forwarded_messages.json'):
        self.storage_file = storage_file
        self.forwarded_messages = set()
        self._load_from_file()
    
    def _load_from_file(self):
        """Load forwarded message IDs from JSON file"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    self.forwarded_messages = set(data)
                logger.info(f"Loaded {len(self.forwarded_messages)} message IDs from {self.storage_file}")
        except Exception as e:
            logger.error(f"Error loading message IDs from file: {str(e)}")
    
    def _save_to_file(self):
        """Save forwarded message IDs to JSON file"""
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(list(self.forwarded_messages), f)
        except Exception as e:
            logger.error(f"Error saving message IDs to file: {str(e)}")
    
    def is_forwarded(self, message_id):
        """Check if a message was already forwarded"""
        return message_id in self.forwarded_messages
    
    def mark_as_forwarded(self, message_id):
        """Mark a message as forwarded"""
        self.forwarded_messages.add(message_id)
        self._save_to_file()
