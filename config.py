"""
Configuration module for the Telegram Message Forwarder
Supports multiple forwarding rules.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

class Config:
    """Configuration class for the Telegram Message Forwarder"""
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        # Общие настройки API и сессии
        self.api_id = None
        self.api_hash = None
        self.session_string = None
        # Список правил пересылки
        self.rules = []
        
        # Параметры по умолчанию для отдельных правил (могут переопределяться)
        self.replacement_image_path = 'replacement_image.png'
        self.rate_limit_delay = 3
        self.always_replace_media = False
        self.forward_all_messages = True
        self.replace_captioned_only = True
        
        # Загрузка конфигурации
        self._load_config()
        self._load_rules()
    
    def _load_config(self):
        """Load API credentials and session string from environment or file"""
        # Сначала загружаем общие параметры из переменных окружения
        self.api_id = os.getenv('TELEGRAM_API_ID') or os.getenv('API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH') or os.getenv('API_HASH')
        self.session_string = os.getenv('SESSION_STRING')
        
        # Если не заданы в окружении, пробуем из файла
        if not all([self.api_id, self.api_hash, self.session_string]):
            try:
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r') as f:
                        config_data = json.load(f)
                    self.api_id = config_data.get('api_id', self.api_id)
                    self.api_hash = config_data.get('api_hash', self.api_hash)
                    self.session_string = config_data.get('session_string', self.session_string)
                    # Также загружаем общие настройки
                    self.replacement_image_path = config_data.get('replacement_image_path', self.replacement_image_path)
                    self.rate_limit_delay = config_data.get('rate_limit_delay', self.rate_limit_delay)
                    self.always_replace_media = config_data.get('always_replace_media', self.always_replace_media)
                    self.forward_all_messages = config_data.get('forward_all_messages', self.forward_all_messages)
            except Exception as e:
                logger.error(f"Error loading config file: {str(e)}")
    
    def _load_rules(self):
        """Load forwarding rules from environment variable RULES (JSON) or from old-style variables"""
        rules_json = os.getenv('RULES')
        if rules_json:
            try:
                rules_data = json.loads(rules_json)
                if isinstance(rules_data, list):
                    for rule in rules_data:
                        # Проверяем наличие обязательных полей
                        if 'source' in rule and 'destination' in rule:
                            self.rules.append({
                                'source': str(rule['source']),
                                'destination': str(rule['destination']),
                                'filters': rule.get('filters', '')
                            })
                    logger.info(f"Loaded {len(self.rules)} rules from RULES environment variable")
                else:
                    logger.error("RULES must be a JSON array")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in RULES variable: {e}")
        else:
            # Поддержка старого формата (одно правило)
            source = os.getenv('SOURCE_CHANNEL')
            dest = os.getenv('DESTINATION_CHANNEL')
            if source and dest:
                # Получаем фильтры из TEXT_FILTERS (может быть строкой или JSON-списком)
                filters = os.getenv('TEXT_FILTERS', '')
                self.rules.append({
                    'source': source,
                    'destination': dest,
                    'filters': filters
                })
                logger.info("Loaded single rule from legacy environment variables")
    
    def is_valid(self):
        """Check if the configuration is valid"""
        if not self.api_id or not self.api_hash or not self.session_string:
            logger.error("Missing required API credentials or session string")
            return False
        if not self.rules:
            logger.error("No forwarding rules defined")
            return False
        return True
    
    def save(self):
        """Save configuration to file (optional)"""
        config_data = {
            'api_id': self.api_id,
            'api_hash': self.api_hash,
            'session_string': self.session_string,
            'replacement_image_path': self.replacement_image_path,
            'rate_limit_delay': self.rate_limit_delay,
            'always_replace_media': self.always_replace_media,
            'forward_all_messages': self.forward_all_messages,
            'rules': self.rules
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=4)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving config file: {str(e)}")
