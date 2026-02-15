"""
Telegram message forwarding implementation
Supports multiple forwarding rules and keyword whitelist filtering.
"""

import os
import re
import logging
import asyncio
import traceback
from datetime import datetime
from telethon import events, utils
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, PeerChannel, PeerChat
from telethon.errors import FloodWaitError, ChatAdminRequiredError

from filter_manager import TextFilterManager
from db_handler import MessageTracker

logger = logging.getLogger(__name__)

class TelegramForwarder:
    """Handles forwarding messages from source to destination channel with keyword filtering"""
    
    def __init__(self, client, source, destination, filters='', tracker=None, rate_limit_delay=3):
        """
        Initialize a forwarder for one rule.
        
        :param client: Telethon client instance
        :param source: source channel identifier (username, ID or link)
        :param destination: destination channel identifier
        :param filters: comma-separated keywords or list of keywords
        :param tracker: optional shared MessageTracker instance
        :param rate_limit_delay: seconds to wait between messages
        """
        self.client = client
        self.source = source
        self.destination = destination
        self.filter_manager = TextFilterManager(filters)
        self.tracker = tracker if tracker is not None else MessageTracker()
        self.rate_limit_delay = rate_limit_delay
        
        self.running = False
        self.last_message_time = datetime.now()
        self.source_entity = None
        self.dest_entity = None

    async def start_forwarding(self):
        """Start forwarding messages from source to destination"""
        if self.running:
            logger.warning(f"Forwarder for {self.source} -> {self.destination} is already running")
            return

        self.running = True
        logger.info(f"Starting to forward messages from {self.source} to {self.destination}")

        # Load all dialogs to populate cache (if not already loaded)
        try:
            logger.info("Fetching all dialogs to populate cache...")
            await self.client.get_dialogs()
            logger.info("Dialogs fetched successfully.")
        except Exception as e:
            logger.warning(f"Could not fetch dialogs: {e}")

        # Resolve source and destination entities
        async def resolve_entity(identifier: str):
            """Resolve entity from string (ID, username, link)"""
            try:
                id_val = int(identifier)
                # Try different ways to get entity by ID
                try:
                    return await self.client.get_entity(id_val)
                except Exception:
                    if id_val < 0:
                        if str(id_val).startswith('-100'):
                            # Supergroup or channel
                            return await self.client.get_entity(PeerChannel(id_val))
                        else:
                            # Regular group – try positive ID
                            logger.info(f"Trying positive ID {abs(id_val)} for group {id_val}")
                            return await self.client.get_entity(abs(id_val))
                    else:
                        # Positive number – try as chat or user
                        try:
                            return await self.client.get_entity(PeerChat(id_val))
                        except:
                            return await self.client.get_entity(id_val)
            except ValueError:
                # Not a number: username or link
                channel = identifier
                if channel.startswith('https://t.me/'):
                    channel = '@' + channel[13:].split('/')[0]
                elif channel.startswith('t.me/'):
                    channel = '@' + channel[5:].split('/')[0]
                elif not channel.startswith('@') and not channel.startswith('https://'):
                    channel = '@' + channel
                return await self.client.get_entity(channel)

        try:
            self.source_entity = await resolve_entity(self.source)
            self.dest_entity = await resolve_entity(self.destination)
            
            logger.info(f"Resolved source: {getattr(self.source_entity, 'title', self.source_entity.id)} (ID: {self.source_entity.id})")
            logger.info(f"Resolved destination: {getattr(self.dest_entity, 'title', self.dest_entity.id)} (ID: {self.dest_entity.id})")
            
        except Exception as e:
            logger.error(f"Error resolving channels for rule {self.source} -> {self.destination}: {e}")
            self.running = False
            return

        # Register event handler for new messages
        logger.info(f"Setting up event handler for source channel: {self.source_entity.id}")
        
        @self.client.on(events.NewMessage(chats=self.source_entity))
        async def on_new_message(event):
            try:
                logger.info(f"New message detected from {self.source}: {event.message.id}")
                
                if self.tracker.is_forwarded(event.message.id):
                    logger.info(f"Message {event.message.id} was already forwarded. Skipping.")
                    return
                
                await self._apply_rate_limit()
                await self._forward_message(event)
                self.last_message_time = datetime.now()
                logger.info(f"Successfully processed message {event.message.id} from {self.source}")
                
            except FloodWaitError as e:
                logger.warning(f"Rate limit hit. Sleeping for {e.seconds} seconds")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Error forwarding message {event.message.id}: {str(e)}")
                logger.debug(traceback.format_exc())

    async def _apply_rate_limit(self):
        """Apply rate limiting to avoid flood errors"""
        now = datetime.now()
        elapsed = (now - self.last_message_time).total_seconds()
        if elapsed < self.rate_limit_delay:
            delay = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: sleeping for {delay:.2f} seconds")
            await asyncio.sleep(delay)

    async def _forward_message(self, event):
        """Process and forward a message to the destination channel"""
        message = event.message
        
        # Extract text (either message text or caption)
        message_text = ""
        if hasattr(message, 'text') and message.text:
            message_text = message.text
        elif hasattr(message, 'caption') and message.caption:
            message_text = message.caption

        # Apply keyword whitelist filtering
        if not self.filter_manager.contains_keyword(message_text):
            logger.info(f"Message {message.id} does not contain any keywords. Skipping.")
            self.tracker.mark_as_forwarded(message.id)
            return

        # Use original text (no modification)
        filtered_text = message_text

        try:
            # Determine if message has media and what type
            has_media = hasattr(message, 'media') and message.media
            is_photo = has_media and isinstance(message.media, MessageMediaPhoto)
            is_document = has_media and isinstance(message.media, MessageMediaDocument)
            has_caption = bool(message_text)

            # Decide how to forward (with/without replacement)
            # This part is kept as in original, but uses self.dest_entity for destination
            if has_media and (is_photo or is_document) and has_caption:
                logger.info(f"Forwarding message {message.id} with replacement image (has caption)")
                await self._forward_with_replacement(message, filtered_text)
            elif has_media and (is_photo or is_document):
                # Media without caption – decide based on config (hardcoded to not replace here)
                logger.info(f"Forwarding message {message.id} without replacement (media without caption)")
                await self._forward_standard(message, filtered_text)
            else:
                # Text only
                logger.info(f"Forwarding text message {message.id}")
                await self._forward_standard(message, filtered_text)

            self.tracker.mark_as_forwarded(message.id)

        except Exception as e:
            logger.error(f"Error while forwarding message {message.id}: {str(e)}")
            logger.debug(traceback.format_exc())

    async def _forward_standard(self, message, filtered_text):
        """Forward a message without special handling (re‑upload method)"""
        destination = self.dest_entity  # use resolved entity
        
        # Safely check attributes
        has_text = hasattr(message, 'text') and message.text
        has_caption = hasattr(message, 'caption') and message.caption
        has_media = hasattr(message, 'media') and message.media

        try:
            if has_media:
                try:
                    # Download media bytes
                    media = await self.client.download_media(message.media, file=bytes)
                    
                    # Determine if it's an image (to send as photo)
                    is_image = is_photo = isinstance(message.media, MessageMediaPhoto)
                    filename = None
                    if not is_photo and hasattr(message.media, 'document'):
                        doc = message.media.document
                        # Check MIME type
                        if hasattr(doc, 'mime_type') and doc.mime_type.startswith('image/'):
                            is_image = True
                        # Try to get filename
                        for attr in doc.attributes:
                            if hasattr(attr, 'file_name') and attr.file_name:
                                filename = attr.file_name
                                break

                    if is_image:
                        # Send as photo (force_document=False)
                        await self.client.send_file(
                            destination,
                            media,
                            caption=filtered_text,
                            force_document=False,
                            file_name=filename or "image.jpg"
                        )
                    else:
                        # Send as document
                        await self.client.send_file(
                            destination,
                            media,
                            caption=filtered_text,
                            force_document=True,
                            file_name=filename or "file"
                        )
                except Exception as e:
                    logger.error(f"Error downloading/sending media: {e}. Sending text only.")
                    await self.client.send_message(destination, filtered_text)
            else:
                # Text only
                await self.client.send_message(destination, filtered_text)
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            # Fallback to text only
            try:
                await self.client.send_message(destination, filtered_text)
            except Exception as e2:
                logger.error(f"Even text fallback failed: {str(e2)}")

    async def _forward_with_replacement(self, message, filtered_text):
        """Forward a message with the image replaced by a fixed replacement image."""
        destination = self.dest_entity
        fixed_image_path = 'replacement_image.png'  # must exist in working directory
        
        try:
            # Clean up filtered text (optional, kept from original)
            if filtered_text:
                lines = filtered_text.split('\n')
                clean_lines = []
                for line in lines:
                    # Remove lines containing unwanted patterns (if any)
                    if any(pattern in line.lower() for pattern in [
                        "register here", "إنــضــم", "code", "tarekteam", "deposit", "bounus"
                    ]):
                        continue
                    # Replace @tarekrash3d with @Gazew_07 if needed
                    if "@tarekrash3d" in line:
                        line = line.replace("@tarekrash3d", "@Gazew_07")
                    clean_lines.append(line)
                filtered_text = '\n'.join(clean_lines)

            # Send the replacement image
            if os.path.exists(fixed_image_path):
                await self.client.send_file(
                    destination,
                    fixed_image_path,
                    caption=filtered_text,
                    force_document=False,
                    file_name="billionaire_ai_bot.png"
                )
            else:
                logger.warning(f"Replacement image {fixed_image_path} not found. Sending text only.")
                await self.client.send_message(destination, filtered_text)
        except Exception as e:
            logger.error(f"Error in replacement handling: {e}. Sending text only.")
            try:
                await self.client.send_message(destination, filtered_text)
            except Exception as e2:
                logger.error(f"Text fallback failed: {e2}")
