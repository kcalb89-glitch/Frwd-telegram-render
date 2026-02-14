"""
Telegram message forwarding implementation
"""

import os
import re
import logging
import asyncio
import traceback
from datetime import datetime
from telethon import events, utils
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from telethon.errors import FloodWaitError, ChatAdminRequiredError

from filter_manager import TextFilterManager
from db_handler import MessageTracker

logger = logging.getLogger(__name__)

class TelegramForwarder:
    """Handles forwarding messages from source to destination channel"""
    
    def __init__(self, client, config, tracker=None):
        """Initialize the TelegramForwarder with a client, config, and optional tracker"""
        self.client = client
        self.config = config
        self.filter_manager = TextFilterManager(config.text_filters)
        
        # Use the provided tracker or create a new one
        self.tracker = tracker if tracker is not None else MessageTracker()
        
        self.running = False
        self.last_message_time = datetime.now()
        # Initialize channel IDs
        self.source_id = None
        self.dest_id = None

    async def start_forwarding(self):
        if self.running:
            logger.warning("Forwarder is already running")
            return

        self.running = True
        logger.info(f"Starting to forward messages from {self.config.source_channel} to {self.config.destination_channel}")

    # Загружаем все диалоги, чтобы заполнить кеш Telethon
        try:
            logger.info("Fetching all dialogs to populate cache...")
            await self.client.get_dialogs()
            try:
                logger.info("--- Список всех доступных диалогов ---")
                dialogs = await self.client.get_dialogs()
                for dialog in dialogs:
                    entity = dialog.entity
                    name = getattr(entity, 'title', getattr(entity, 'first_name', 'Unknown'))
                    logger.info(f"Chat: {name} (ID: {entity.id})")
                logger.info("--- Конец списка ---")
            except Exception as e:
                logger.error(f"Error listing dialogs: {e}")
             logger.info("Dialogs fetched successfully.")
        except Exception as e:
            logger.warning(f"Could not fetch dialogs: {e}")

        source_raw = self.config.source_channel.strip()
        dest_raw = self.config.destination_channel.strip()

        async def resolve_entity(identifier: str):
            """Resolve entity from string (ID, username, link)"""
            from telethon.tl.types import PeerChannel, PeerChat
    
        # Пробуем интерпретировать как число
            try:
                id_val = int(identifier)
            # Определяем тип чата по ID
                if id_val < 0:
                    if str(id_val).startswith('-100'):
                    # Супергруппа или канал
                        return await self.client.get_entity(PeerChannel(id_val))
                    else:
                    # Обычная группа
                        return await self.client.get_entity(PeerChat(id_val))
                else:
                # Положительное число — возможно пользователь или канал с положительным ID
                    return await self.client.get_entity(id_val)
            except ValueError:
            # Не число — обрабатываем как username или ссылку
                channel = identifier
                if channel.startswith('https://t.me/'):
                    channel = '@' + channel[13:].split('/')[0]
                elif channel.startswith('t.me/'):
                    channel = '@' + channel[5:].split('/')[0]
                elif not channel.startswith('@') and not channel.startswith('https://'):
                    channel = '@' + channel
                return await self.client.get_entity(channel)

        try:
            source_entity = await resolve_entity(source_raw)
            dest_entity = await resolve_entity(dest_raw)

        # Логируем результат
            source_info = f"title: '{getattr(source_entity, 'title', 'Unknown')}'"
            if hasattr(source_entity, 'username') and source_entity.username:
                source_info += f", username: @{source_entity.username}"
            logger.info(f"Successfully resolved source channel: {source_info} (ID: {source_entity.id})")

            dest_info = f"title: '{getattr(dest_entity, 'title', 'Unknown')}'"
            if hasattr(dest_entity, 'username') and dest_entity.username:
                dest_info += f", username: @{dest_entity.username}"
            logger.info(f"Successfully resolved destination channel: {dest_info} (ID: {dest_entity.id})")

            self.source_id = source_entity.id
            self.dest_id = dest_entity.id

        except Exception as e:
            logger.error(f"Error resolving channels: {e}")
            logger.error("Make sure you have joined both the source and destination channels.")
            logger.error("For private channels, your account must be a member of the channel.")
            logger.error("You can specify channels in several formats:")
            logger.error("1. Channel ID with -100 prefix: -1001234567890")
            logger.error("2. Channel ID without prefix: 1234567890")
            logger.error("3. Channel username with @: @channel_name")
            logger.error("4. Channel username without @: channel_name")
            logger.error("5. Channel invite link: https://t.me/channel_name")
            self.running = False
            return

    # Регистрация обработчика событий
        logger.info(f"Setting up event handler for source channel: {source_entity.id}")
        @self.client.on(events.NewMessage(chats=source_entity))
        async def on_new_message(event):
        # ... остальной код (без изменений, как в вашем файле)
        # Вставьте сюда код обработчика из вашего исходного файла, начиная с try:
            try:
                logger.info(f"New message detected: {event.message.id}")
                if self.tracker.is_forwarded(event.message.id):
                    logger.info(f"Message {event.message.id} was already forwarded. Skipping.")
                    return
                await self._apply_rate_limit()
                logger.info(f"Processing message {event.message.id} for forwarding")
                await self._forward_message(event)
                self.last_message_time = datetime.now()
                logger.info(f"Successfully processed message {event.message.id}")
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
        
        if elapsed < self.config.rate_limit_delay:
            delay = self.config.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: sleeping for {delay:.2f} seconds")
            await asyncio.sleep(delay)
    
    async def _forward_message(self, event):
        """Process and forward a message to the destination channel"""
        message = event.message
        
        # Apply text filters if there's text in the message
        # Safely access attributes that might not exist
        message_text = ""
        if hasattr(message, 'text') and message.text:
            message_text = message.text
        elif hasattr(message, 'caption') and message.caption:
            message_text = message.caption
            
        if message_text:
            # Apply text filters
            filtered_text = self.filter_manager.apply_filters(message_text)
            
            if filtered_text != message_text:
                logger.info(f"Text filtered for message {message.id}")
                # If the text was completely filtered out and there's no media, skip the message
                if not filtered_text and not message.media:
                    logger.info(f"Message {message.id} filtered out completely. Skipping.")
                    self.tracker.mark_as_forwarded(message.id)
                    return
        else:
            filtered_text = message_text
            
        try:
            # Handle different message types with more robust detection
            # Use proper caption detection - only replace images with REAL captions
            has_caption = False
            
            # First, direct attribute check
            if hasattr(message, 'caption') and message.caption:
                has_caption = True
                logger.info(f"Caption directly detected on message {message.id}: {message.caption}")
            
            # Let's debug the full message content
            logger.info(f"Raw message {message.id} attributes: {dir(message)}")
            
            # Check for media content 
            has_media = hasattr(message, 'media') and message.media
            
            # Additional checks for different types of media
            is_photo_or_document = False
            if has_media:
                try:
                    # Better media type identification
                    is_photo = isinstance(message.media, MessageMediaPhoto)
                    is_document = isinstance(message.media, MessageMediaDocument)
                    is_photo_or_document = is_photo or is_document
                    
                    # Log detailed media information
                    if is_photo:
                        logger.info(f"Message {message.id} has PHOTO media")
                    if is_document:
                        logger.info(f"Message {message.id} has DOCUMENT media")
                    
                    # IMPORTANT DEBUG: Dump all attributes of the message
                    # This will help understand what's available in the message object
                    if hasattr(message, '__dict__'):
                        logger.info(f"Message dict: {message.__dict__}")
                    
                    # Reset caption detection to be more specific
                    has_caption = False
                    
                    # Method 1: Direct caption attribute
                    if hasattr(message, 'caption') and message.caption:
                        has_caption = True
                        logger.info(f"Direct caption found: {message.caption}")
                    
                    # Method 2: For photos with MessageMediaPhoto
                    if is_photo and hasattr(message, 'message') and message.message:
                        # In Telegram, photos often have their caption in the message attribute
                        has_caption = True
                        logger.info(f"Photo caption found in message attribute: {message.message}")
                    
                    # Method 3: Check message.raw_text which often contains captions
                    if hasattr(message, 'raw_text') and message.raw_text:
                        logger.info(f"Raw text found which might be caption: {message.raw_text}")
                        # Only treat as caption if it's not a regular text message
                        if is_photo or is_document:
                            has_caption = True
                            
                    # Super explicit logging of caption values
                    logger.info(f"Caption detection for message {message.id}: "
                               f"caption={getattr(message, 'caption', None)}, "
                               f"message={getattr(message, 'message', None)}, "
                               f"raw_text={getattr(message, 'raw_text', None)}")
                        
                except (AttributeError, TypeError) as e:
                    logger.warning(f"Error identifying media type for message {message.id}: {str(e)}")
                    is_photo_or_document = False
            
            # Always log complete media status for debugging
            logger.info(f"Message {message.id} status: has_caption={has_caption}, has_media={has_media}, is_photo_or_document={is_photo_or_document}")
            
            # Check if we should only replace captioned images
            caption_only_mode = getattr(self.config, 'replace_captioned_only', True)
            logger.info(f"Caption-only mode: {caption_only_mode}")
            
            # Only replace images with captions if caption_only_mode is True
            if has_media and is_photo_or_document and (has_caption or not caption_only_mode):
                # Only replace captioned images with the Billionaire AI Bot image
                logger.info(f"Forwarding message {message.id} with Billionaire AI Bot replacement image (has caption)")
                # Override the image path to ensure we use PNG
                self.config.replacement_image_path = 'replacement_image.png'
                # Log the file info to debug
                logger.info(f"Using PNG image: {os.path.exists('replacement_image.png')}, size: {os.path.getsize('replacement_image.png') if os.path.exists('replacement_image.png') else 'not found'}")
                await self._forward_with_replacement(message, filtered_text)
            elif has_media and is_photo_or_document and self.config.always_replace_media:
                # Only replace other media if the always_replace_media flag is set
                logger.info(f"Forwarding message {message.id} with replaced image (always replace mode)")
                await self._forward_with_replacement(message, filtered_text)
            else:
                # Standard message forwarding for all other cases
                logger.info(f"Forwarding message {message.id}")
                await self._forward_standard(message, filtered_text)
            
            # Mark as forwarded in our tracker
            self.tracker.mark_as_forwarded(message.id)
            
        except Exception as e:
            logger.error(f"Error while forwarding message {message.id}: {str(e)}")
            logger.debug(traceback.format_exc())
    
    async def _forward_standard(self, message, filtered_text):
        """Forward a message without special handling"""
        # Use the resolved destination id if available
        destination = getattr(self, 'dest_id', self.config.destination_channel)
        
        # Safely check if text is present and was filtered
        has_text = hasattr(message, 'text') and message.text
        has_caption = hasattr(message, 'caption') and message.caption
        has_media = hasattr(message, 'media') and message.media
        
        # Check if filtering was applied
        text_filtered = (has_text and message.text != filtered_text) or (has_caption and message.caption != filtered_text)
        
        # Always use re-upload method instead of forwarding to bypass restrictions
        try:
            if has_media:
                try:
                    # Detect the media type and filename
                    filename = None
                    # Determine if it's a photo
                    is_photo = False
                    if hasattr(message.media, 'photo'):
                        is_photo = True
                        filename = 'photo.jpg'
                    elif hasattr(message.media, 'document'):
                        # Try to get the original filename from the document
                        if hasattr(message.media.document, 'attributes'):
                            for attr in message.media.document.attributes:
                                if hasattr(attr, 'file_name') and attr.file_name:
                                    filename = attr.file_name
                                    break
                                
                    # Download the media with proper filename attributes
                    if filename:
                        logger.info(f"Downloading media as {filename}")
                        media = await self.client.download_media(message.media, file=bytes)
                    else:
                        # Auto-detect if no filename available
                        media = await self.client.download_media(message.media, file=bytes)
                    
                    # For clearer logging
                    media_type = "photo" if is_photo else "document"
                    logger.info(f"Downloaded media of type: {media_type}")
                    
                    # Detect if it's a photo or image-like document (common in restricted channels)
                    is_image = is_photo
                    if not is_photo and hasattr(message.media, 'document'):
                        # Check MIME type if available
                        if hasattr(message.media.document, 'mime_type'):
                            is_image = message.media.document.mime_type.startswith('image/')
                        
                        # Check file extension if we have a filename
                        if filename:
                            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
                            is_image = any(filename.lower().endswith(ext) for ext in image_extensions)
                    
                    # For all image types, we'll handle them differently
                    if is_image:
                        # First, save the bytes to a temporary file
                        # This ensures we have proper file extension for accurate MIME detection
                        logger.info("Media is an image, saving to temporary file first")
                        import tempfile
                        import mimetypes
                        
                        # Determine the best extension by MIME type or default to jpg
                        ext = '.jpg'  # Default extension
                        if hasattr(message.media, 'document') and hasattr(message.media.document, 'mime_type'):
                            # Get extension from MIME type
                            mime_ext = mimetypes.guess_extension(message.media.document.mime_type)
                            if mime_ext:
                                ext = mime_ext
                        elif filename and '.' in filename:
                            # Get extension from original filename
                            file_ext = '.' + filename.split('.')[-1].lower()
                            if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
                                ext = file_ext
                        
                        # Create a temporary file with the correct extension
                        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                            temp_file.write(media)
                            temp_path = temp_file.name
                            
                        logger.info(f"Saved image to temporary file: {temp_path} with extension {ext}")
                        
                        try:
                            # Send the file directly from the temp file path
                            # This lets Telethon detect proper MIME type and handle as photo
                            logger.info("Sending as photo from temporary file")
                            await self.client.send_file(
                                destination,
                                temp_path,
                                caption=filtered_text,
                                force_document=False,  # Never send as document
                            )
                            
                            # Clean up the temporary file
                            try:
                                os.unlink(temp_path)
                            except Exception as cleanup_error:
                                logger.error(f"Error deleting temporary file: {str(cleanup_error)}")
                                
                        except Exception as img_error:
                            logger.error(f"Error sending as photo from temp file: {str(img_error)}. Trying bytes directly.")
                            try:
                                # Try alternative method with direct bytes
                                await self.client.send_file(
                                    destination,
                                    media,
                                    caption=filtered_text,
                                    force_document=False,
                                    file_name=f"image{ext}"  # Explicit naming with correct extension
                                )
                            except Exception as direct_error:
                                logger.error(f"Error sending bytes directly: {str(direct_error)}. Last resort approach.")
                                # Last resort - try without explicit file_name
                                await self.client.send_file(
                                    destination,
                                    media,
                                    caption=filtered_text
                                )
                            
                            # Clean up the temporary file if it still exists
                            try:
                                if os.path.exists(temp_path):
                                    os.unlink(temp_path)
                            except Exception:
                                pass
                    else:
                        # For actual documents, preserve the original attributes
                        logger.info(f"Media is a document, sending as file with name: {filename}")
                        try:
                            await self.client.send_file(
                                destination,
                                media,
                                caption=filtered_text,
                                force_document=True,  # Force as document
                                file_name=filename if filename else "document",
                                attributes=message.media.document.attributes if hasattr(message.media, 'document') and hasattr(message.media.document, 'attributes') else None
                            )
                        except Exception as doc_error:
                            logger.error(f"Error sending document: {str(doc_error)}. Trying simplified approach.")
                            # Try with minimal parameters
                            await self.client.send_file(
                                destination,
                                media,
                                caption=filtered_text,
                                file_name=filename if filename else "document"
                            )
                except Exception as e:
                    logger.error(f"Error downloading media: {str(e)}. Sending as text-only.")
                    await self.client.send_message(
                        destination,
                        filtered_text
                    )
            else:
                # Just send the text
                await self.client.send_message(
                    destination,
                    filtered_text
                )
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            # If we encounter a ForwardMessagesRequest error, try again with re-upload method
            if "ForwardMessagesRequest" in str(e):
                logger.info("Protected chat detected, using alternative upload method")
                try:
                    if has_text or has_caption:
                        await self.client.send_message(
                            destination,
                            filtered_text
                        )
                except Exception as send_error:
                    logger.error(f"Failed to send message text: {str(send_error)}")
    
    async def _forward_with_replacement(self, message, filtered_text):
        """Forward a message with the image replaced by our replacement image - The Billionaire AI Bot image"""
        # Use the resolved destination id if available
        destination = getattr(self, 'dest_id', self.config.destination_channel)
        
        try:
            # IMPORTANT: Always hardcode the PNG path to ensure we use the right image
            fixed_image_path = 'replacement_image.png'
            logger.info(f"Replacing image for message {message.id} with Billionaire AI Bot PNG image")
            logger.info(f"Fixed Replacement image path: {fixed_image_path}")
            
            # Detailed file checks
            abs_path = os.path.abspath(fixed_image_path)
            exists = os.path.exists(fixed_image_path)
            
            logger.info(f"Absolute path: {abs_path}")
            logger.info(f"File exists: {exists}")
            
            if exists:
                size = os.path.getsize(fixed_image_path)
                logger.info(f"File size: {size} bytes")
                
                # Always force PNG extension
                ext = '.png'
                logger.info(f"Forcing image extension: {ext}")
                
                # APPROACH 1: Use a temporary file (usually most reliable)
                import tempfile
                import shutil
                
                try:
                    # Create a temp file with .png extension
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        tmp_path = tmp.name
                    
                    # Copy the image to the temp file
                    shutil.copy2(fixed_image_path, tmp_path)
                    logger.info(f"Created temporary copy at: {tmp_path}")
                    
                    # Clean up the filtered text by removing problematic lines
                    if filtered_text:
                        lines = filtered_text.split('\n')
                        clean_lines = []
                        for line in lines:
                            # Skip any line containing these problematic patterns
                            if any(pattern in line.lower() for pattern in [
                                "register here", 
                                "إنــضــم", 
                                "code", 
                                "tarekteam", 
                                "deposit", 
                                "bounus"
                            ]):
                                logger.info(f"Removing problematic line: {line}")
                                continue
                                
                            # Remove URL hidden behind text (text wrapped in ** and with `` format)
                            # This pattern: **text**
                            line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
                            # This pattern: `text`
                            line = re.sub(r'`([^`]+)`', r'\1', line)
                            # Remove any remaining markdown link format: [text](url)
                            line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
                            
                            # Replace @tarekrash3d with @Gazew_07
                            if "@tarekrash3d" in line:
                                line = line.replace("@tarekrash3d", "@Gazew_07")
                            clean_lines.append(line)
                        
                        # Re-assemble the text from clean lines
                        filtered_text = '\n'.join(clean_lines)
                    
                    # Send the image from the temp file
                    logger.info(f"Sending replacement PNG image with caption (length: {len(filtered_text) if filtered_text else 0})")
                    await self.client.send_file(
                        destination,
                        tmp_path,
                        caption=filtered_text,
                        force_document=False,  # Always send as photo
                        file_name="billionaire_ai_bot.png"  # Force PNG filename
                    )
                    
                    # Clean up the temp file
                    try:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    except Exception as cleanup_error:
                        logger.warning(f"Error cleaning up temp file: {str(cleanup_error)}")
                    
                    # If we reach here, the send was successful
                    logger.info(f"Successfully sent replacement PNG image for message {message.id}")
                    return
                    
                except Exception as temp_error:
                    logger.warning(f"Temp file approach failed: {str(temp_error)}. Trying direct file...")
                    
                    # Clean up temp file if it exists
                    try:
                        if 'tmp_path' in locals() and os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    except Exception:
                        pass
                
                # APPROACH 2: Direct file path
                try:
                    # Clean up the filtered text again (in case it was changed since first attempt)
                    if filtered_text:
                        lines = filtered_text.split('\n')
                        clean_lines = []
                        for line in lines:
                            # Skip any line containing these problematic patterns
                            if any(pattern in line.lower() for pattern in [
                                "register here", 
                                "إنــضــم", 
                                "code", 
                                "tarekteam", 
                                "deposit", 
                                "bounus"
                            ]):
                                logger.info(f"Removing problematic line (approach 2): {line}")
                                continue
                                
                            # Remove URL hidden behind text (text wrapped in ** and with `` format)
                            # This pattern: **text**
                            line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
                            # This pattern: `text`
                            line = re.sub(r'`([^`]+)`', r'\1', line)
                            # Remove any remaining markdown link format: [text](url)
                            line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
                            
                            # Replace @tarekrash3d with @Gazew_07
                            if "@tarekrash3d" in line:
                                line = line.replace("@tarekrash3d", "@Gazew_07")
                            clean_lines.append(line)
                        
                        # Re-assemble the text from clean lines
                        filtered_text = '\n'.join(clean_lines)
                    
                    logger.info("Using direct file path approach")
                    await self.client.send_file(
                        destination,
                        fixed_image_path,
                        caption=filtered_text,
                        force_document=False,
                        file_name="billionaire_ai_bot.png"  # Force PNG filename
                    )
                    logger.info(f"Successfully sent replacement PNG image using direct path")
                    return
                    
                except Exception as direct_error:
                    logger.warning(f"Direct file approach failed: {str(direct_error)}. Trying bytes...")
                
                # APPROACH 3: File bytes
                try:
                    # Clean up the filtered text again (in case it was changed since previous attempts)
                    if filtered_text:
                        lines = filtered_text.split('\n')
                        clean_lines = []
                        for line in lines:
                            # Skip any line containing these problematic patterns
                            if any(pattern in line.lower() for pattern in [
                                "register here", 
                                "إنــضــم", 
                                "code", 
                                "tarekteam", 
                                "deposit", 
                                "bounus"
                            ]):
                                logger.info(f"Removing problematic line (approach 3): {line}")
                                continue
                                
                            # Remove URL hidden behind text (text wrapped in ** and with `` format)
                            # This pattern: **text**
                            line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
                            # This pattern: `text`
                            line = re.sub(r'`([^`]+)`', r'\1', line)
                            # Remove any remaining markdown link format: [text](url)
                            line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
                            
                            # Replace @tarekrash3d with @Gazew_07
                            if "@tarekrash3d" in line:
                                line = line.replace("@tarekrash3d", "@Gazew_07")
                            clean_lines.append(line)
                        
                        # Re-assemble the text from clean lines
                        filtered_text = '\n'.join(clean_lines)
                    
                    logger.info("Using file bytes approach")
                    with open(fixed_image_path, 'rb') as img_file:
                        img_bytes = img_file.read()
                    
                    logger.info(f"Read {len(img_bytes)} bytes from the PNG image file")
                    await self.client.send_file(
                        destination,
                        img_bytes,
                        caption=filtered_text,
                        force_document=False,
                        file_name="billionaire_ai_bot.png"  # Force PNG filename
                    )
                    logger.info(f"Successfully sent replacement PNG image using bytes")
                    return
                    
                except Exception as bytes_error:
                    logger.error(f"All approaches failed: {str(bytes_error)}")
            
            # If we reach here, all approaches failed or the file doesn't exist
            # Final text cleanup for fallback
            if filtered_text:
                lines = filtered_text.split('\n')
                clean_lines = []
                for line in lines:
                    # Skip any line containing these problematic patterns
                    if any(pattern in line.lower() for pattern in [
                        "register here", 
                        "إنــضــم", 
                        "code", 
                        "tarekteam", 
                        "deposit", 
                        "bounus"
                    ]):
                        logger.info(f"Removing problematic line (fallback): {line}")
                        continue
                        
                    # Remove URL hidden behind text (text wrapped in ** and with `` format)
                    # This pattern: **text**
                    line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
                    # This pattern: `text`
                    line = re.sub(r'`([^`]+)`', r'\1', line)
                    # Remove any remaining markdown link format: [text](url)
                    line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
                    
                    # Replace @tarekrash3d with @Gazew_07
                    if "@tarekrash3d" in line:
                        line = line.replace("@tarekrash3d", "@Gazew_07")
                    clean_lines.append(line)
                
                # Re-assemble the text from clean lines
                filtered_text = '\n'.join(clean_lines)
            
            logger.warning("Could not send replacement image. Falling back to text-only.")
            await self.client.send_message(
                destination,
                filtered_text if filtered_text else "Message with media"
            )
            
        except Exception as e:
            logger.error(f"Critical error in replacement handling: {str(e)}")
            # Make sure we always at least send the text with lines cleaned
            try:
                # Final desperate text cleanup
                if filtered_text:
                    lines = filtered_text.split('\n')
                    clean_lines = []
                    for line in lines:
                        # Skip any line containing these problematic patterns
                        if any(pattern in line.lower() for pattern in [
                            "register here", 
                            "إنــضــم", 
                            "code", 
                            "tarekteam", 
                            "deposit", 
                            "bounus"
                        ]):
                            continue
                            
                        # Remove URL hidden behind text (text wrapped in ** and with `` format)
                        # This pattern: **text**
                        line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
                        # This pattern: `text`
                        line = re.sub(r'`([^`]+)`', r'\1', line)
                        # Remove any remaining markdown link format: [text](url)
                        line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)
                        
                        # Replace @tarekrash3d with @Gazew_07
                        if "@tarekrash3d" in line:
                            line = line.replace("@tarekrash3d", "@Gazew_07")
                        clean_lines.append(line)
                    
                    # Re-assemble the text from clean lines
                    filtered_text = '\n'.join(clean_lines)
                
                await self.client.send_message(
                    destination,
                    filtered_text if filtered_text else "Message with media" 
                )
            except Exception as text_error:
                logger.error(f"Even text fallback failed: {str(text_error)}")
