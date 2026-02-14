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
    """
    
    def __init__(self, filters=None):
        """
        Initialize the filter manager with a comma-separated string of keywords.
        Example: "срочно,важно,акция"
        """
        self.keywords = []
        if filters and isinstance(filters, str):
            # Разделяем по запятой, убираем лишние пробелы и приводим к нижнему регистру
            raw_keywords = [kw.strip() for kw in filters.split(',') if kw.strip()]
            self.keywords = [kw.lower() for kw in raw_keywords]
            logger.info(f"Loaded keywords: {self.keywords}")
        else:
            logger.info("No keywords provided – all messages will be forwarded.")

    def contains_keyword(self, text):
        """
        Check if the text contains any of the keywords (case-insensitive).
        Returns True if at least one keyword is found, or if no keywords are set.
        """
        if not self.keywords:
            # Нет ключевых слов – пропускаем все сообщения
            return True
        if not text:
            # Пустой текст не содержит ключевых слов
            return False
        text_lower = text.lower()
        for kw in self.keywords:
            if kw in text_lower:
                logger.debug(f"Keyword '{kw}' found in text.")
                return True
        logger.debug("No keywords found in text.")
        return False

    # Оставляем старые методы для обратной совместимости, но они не используются
    def add_filters(self, filters):
        """Not used in keyword mode."""
        pass

    def add_filter(self, filter_rule):
        """Not used in keyword mode."""
        pass

    def apply_filters(self, text):
        """Not used in keyword mode – returns original text."""
        return text

    def clear_filters(self):
        """Not used in keyword mode."""
        pass
