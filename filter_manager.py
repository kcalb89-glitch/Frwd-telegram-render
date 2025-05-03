"""
Text filter manager for Telegram message forwarder
"""

import re
import logging

logger = logging.getLogger(__name__)

class TextFilterManager:
    """
    Manages text filters for messages.
    Filters can be:
    - Simple strings to remove
    - Regex patterns to match and remove
    - Replacement rules in the format "pattern->replacement"
    """
    
    def __init__(self, filters=None):
        """Initialize the filter manager with a list of filters"""
        self.simple_filters = []
        self.regex_filters = []
        self.replacements = []
        
        # Custom special filters guaranteed to work
        self.custom_filters = [
            # Remove code TarekTeam deposit bonus
            (re.compile(r'➪\s*Code:\s*\(\s*TarekTeam\s*\)\s*50%\s*Deposit\s*bounus.*?(\n|$)', re.IGNORECASE | re.MULTILINE), ''),
            
            # Replace REGISTER HERE with proper text
            (re.compile(r'➪\s*REGISTER\s*HERE.*?إنــضــم\s*إلـى\s*فــريقـي.*?(\n|$)', re.IGNORECASE | re.MULTILINE), '➪ Use MTG 1 Step If Loss\n'),
            
            # Remove stars (****) that might appear in URLs or elsewhere
            (re.compile(r'\*\*\*\*'), ''),
            
            # Replace tarekrash3d with Gazew_07
            (re.compile(r'@tarekrash3d'), '@Gazew_07')
        ]
        
        if filters:
            self.add_filters(filters)
    
    def add_filters(self, filters):
        """Add multiple filters at once"""
        for filter_rule in filters:
            self.add_filter(filter_rule)
    
    def add_filter(self, filter_rule):
        """
        Add a filter rule to the manager.
        Filter can be:
        - Simple string: Will be removed from the text
        - Regex pattern: Enclosed in / / will be interpreted as regex
        - Replacement: In the format "pattern->replacement"
        """
        try:
            # Check if it's a replacement rule
            if '->' in filter_rule:
                pattern, replacement = filter_rule.split('->', 1)
                
                # Check if it's a regex replacement
                if pattern.startswith('/') and pattern.endswith('/') and len(pattern) > 2:
                    regex_pattern = pattern[1:-1]
                    try:
                        compiled_regex = re.compile(regex_pattern, re.MULTILINE | re.IGNORECASE)
                        self.replacements.append((compiled_regex, replacement))
                        logger.debug(f"Added regex replacement filter: {regex_pattern} -> {replacement}")
                    except re.error:
                        logger.error(f"Invalid regex pattern: {regex_pattern}")
                else:
                    # Simple string replacement
                    self.replacements.append((pattern, replacement))
                    logger.debug(f"Added simple replacement filter: {pattern} -> {replacement}")
            
            # Check if it's a regex pattern
            elif filter_rule.startswith('/') and filter_rule.endswith('/') and len(filter_rule) > 2:
                regex_pattern = filter_rule[1:-1]
                try:
                    compiled_regex = re.compile(regex_pattern, re.MULTILINE | re.IGNORECASE)
                    self.regex_filters.append(compiled_regex)
                    logger.debug(f"Added regex filter: {regex_pattern}")
                except re.error:
                    logger.error(f"Invalid regex pattern: {regex_pattern}")
            
            # Simple string filter
            else:
                self.simple_filters.append(filter_rule)
                logger.debug(f"Added simple filter: {filter_rule}")
                
        except Exception as e:
            logger.error(f"Error adding filter rule '{filter_rule}': {str(e)}")
    
    def apply_filters(self, text):
        """Apply all filters to the given text"""
        if not text:
            return text
            
        # Log the original text
        logger.info(f"Original text before filtering: '{text}'")
        
        filtered_text = text
        
        # First apply our custom critical filters that must work
        for pattern, replacement in self.custom_filters:
            before = filtered_text
            filtered_text = pattern.sub(replacement, filtered_text)
            if before != filtered_text:
                logger.info(f"Applied custom filter: text changed")
        
        # Apply simple string filters
        for filter_str in self.simple_filters:
            filtered_text = filtered_text.replace(filter_str, '')
        
        # Apply regex filters
        for regex in self.regex_filters:
            filtered_text = regex.sub('', filtered_text)
        
        # Apply replacements
        for pattern, replacement in self.replacements:
            if isinstance(pattern, str):
                # Apply simple string replacement
                filtered_text = filtered_text.replace(pattern, replacement)
            else:  # regex pattern
                filtered_text = pattern.sub(replacement, filtered_text)
        
        # Log the filtered result
        logger.info(f"Text after filtering: '{filtered_text}'")
        
        return filtered_text.strip()
    
    def clear_filters(self):
        """Clear all filters"""
        self.simple_filters = []
        self.regex_filters = []
        self.replacements = []
        # Don't clear custom filters - they're built-in
        logger.debug("All user-defined filters cleared")
