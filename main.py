#!/usr/bin/env python3
"""
Main entry point for the Telegram Message Forwarder with multiple rules.
Includes a simple HTTP server to keep Render happy.
"""

import asyncio
import logging
import sys
import os
import threading
from flask import Flask
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import Config
from forwarder import TelegramForwarder
from db_handler import MessageTracker

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- HTTP-сервер для Render (чтобы был открытый порт) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Forwarder is running."

@app.route('/health')
def health():
    # Можно добавить проверку состояния бота, если нужно
    return "OK", 200

def run_web_server():
    """Запускает Flask-сервер на порту из переменной окружения PORT."""
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port)

# --- Основная асинхронная функция ---
async def main():
    # Загружаем конфигурацию
    config = Config()
    if not config.is_valid():
        logger.error("Invalid configuration. Exiting.")
        sys.exit(1)

    # Создаём клиента Telegram
    client = TelegramClient(
        StringSession(config.session_string),
        int(config.api_id),
        config.api_hash,
        device_model="Render Multi-Forwarder",
        system_version="4.16.30"
    )
    
    await client.start()
    logger.info("Client started successfully")

    # Получаем информацию о себе (для проверки)
    me = await client.get_me()
    logger.info(f"Logged in as {me.first_name} (ID: {me.id})")

    # Загружаем диалоги в кеш (один раз для всех форвардеров)
    try:
        await client.get_dialogs()
        logger.info("Initial dialogs loaded.")
    except Exception as e:
        logger.warning(f"Could not load initial dialogs: {e}")

    # Создаём общий трекер (или отдельные, если нужно)
    tracker = MessageTracker()

    # Создаём и запускаем форвардеры для каждого правила
    forwarders = []
    for rule in config.rules:
        logger.info(f"Creating forwarder for rule: {rule['source']} -> {rule['destination']}")
        fwd = TelegramForwarder(
            client=client,
            source=rule['source'],
            destination=rule['destination'],
            filters=rule['filters'],
            tracker=tracker,
            rate_limit_delay=config.rate_limit_delay
        )
        await fwd.start_forwarding()
        forwarders.append(fwd)

    logger.info(f"Started {len(forwarders)} forwarders. Waiting for messages...")

    # Запускаем HTTP-сервер в отдельном потоке (daemon=True, чтобы он завершился с программой)
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    # Держим клиент подключённым (ждём отключения)
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
