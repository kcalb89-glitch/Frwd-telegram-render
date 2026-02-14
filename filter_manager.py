"""
Text filter manager for Telegram message forwarder
Now supports keyword whitelist filtering.
"""

import logging

logger = logging.getLogger(__name__)

class TextFilterManager:
    """
    Manages keyword filters for messages.
    If keywords are provided, only messages containing at least one keyword are allowed.
    Accepts either a comma-separated string or a list of keywords.
    """
    
    def __init__(self, filters=None):
        """
        Initialize the filter manager.
        filters can be:
        - None or empty: no filtering, all messages pass.
        - string: comma-separated keywords, e.g. "срочно,важно,акция"
        - list: list of keyword strings, e.g. ["срочно", "важно", "акция"]
        """
        self.keywords = []
        if filters:
            if isinstance(filters, str):
                # Разделяем строку по запятой, удаляем лишние пробелы, приводим к нижнему регистру
                raw_keywords = [kw.strip() for kw in filters.split(',') if kw.strip()]
                self.keywords = [kw.lower() for kw in raw_keywords]
                logger.info(f"Loaded keywords from string: {self.keywords}")
            elif isinstance(filters, (list, tuple)):
                # Уже список, просто очищаем и приводим к нижнему регистру
                self.keywords = [str(kw).strip().lower() for kw in filters if kw]
                logger.info(f"Loaded keywords from list: {self.keywords}")
            else:
                logger.warning(f"Unexpected filters type: {type(filters)}. No keywords loaded.")
        else:
            logger.info("No keywords provided – all messages will be forwarded.")

    def contains_keyword(self, text):
        """
        Check if the text contains any of the keywords (case-insensitive).
        Returns True if at least one keyword is found, or if no keywords are set.
        """
        if not self.keywords:
            # Нет ключевых слов – пропускаем все сообщения
            logger.debug("No keywords, forwarding all messages")
            return True
        if not text:
            # Пустой текст не содержит ключевых слов
            logger.debug("Empty text, skipping")
            return False
        text_lower = text.lower()
        for kw in self.keywords:
            if kw in text_lower:
                logger.debug(f"Keyword '{kw}' found in text.")
                return True
        logger.debug(f"No keywords found in text: '{text[:50]}...'")
        return False

    # Оставляем старые методы для обратной совместимости (пустые)
    def add_filters(self, filters):
        pass

    def add_filter(self, filter_rule):
        pass

    def apply_filters(self, text):
        return text

    def clear_filters(self):
        pass
