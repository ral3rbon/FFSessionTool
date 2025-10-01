import os
import json
from typing import Dict, Optional, Union
from PySide6.QtCore import QLocale


class CategorizedTranslator:
    """
    Advanced translation system with categories and automatic English fallback.
    
    Features:
    - JSON-based translation files organized by categories
    - Automatic fallback to English
    - Easy to use tr() function with optional categories
    - Support for placeholders
    - Organized translations (GUI, Messages, Bookmarks, etc.)
    """
    
    def __init__(self, translations_dir: str = "assets/lang/"):
        self.translations_dir = translations_dir
        self.current_language = "en"
        self.translations: Dict[str, Dict[str, str]] = {}  # category -> key -> translation
        self.english_fallback: Dict[str, Dict[str, str]] = {}
        
        # Ensure translations directory exists
        os.makedirs(self.translations_dir, exist_ok=True)
        
        # Load English as fallback
        self._load_language("en")
        self.english_fallback = self.translations.copy()
        
        # Detect system language and load it
        system_locale = QLocale.system().name()[:2]  # e.g., "de" from "de_DE"
        # Use 'en' as fallback if locale is 'C' or empty
        if not system_locale or system_locale.lower() == "c":
            system_locale = "en"
        self.set_language(system_locale)
    
    def _load_language(self, language_code: str) -> bool:
        """Load translations for a specific language."""
        translation_file = os.path.join(self.translations_dir, f"{language_code}.json")
        
        if not os.path.exists(translation_file):
            # Create empty translation file if it doesn't exist
            self._create_empty_translation_file(translation_file)
            return False
        
        try:
            with open(translation_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Handle both old flat format and new categorized format
                if isinstance(data, dict) and any(isinstance(v, dict) for v in data.values()):
                    # New categorized format
                    self.translations = data
                else:
                    # Old flat format - convert to categorized
                    self.translations = {"General": data}
            return True
        except (json.JSONDecodeError, FileNotFoundError):
            self.translations = {}
            return False
    
    def _create_empty_translation_file(self, file_path: str):
        """Create an empty translation file with categorized structure."""
        example_translations = "Placeholder. Will be updated when translations are added over the cli oder gui."
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(example_translations, f, indent=2, ensure_ascii=False)
    
    def set_language(self, language_code: str):
        """Set the current language."""
        self.current_language = language_code
        if not self._load_language(language_code):
            # If loading fails, use English
            self.current_language = "en"
            self.translations = self.english_fallback.copy()
    
    def tr(self, text: str, category: str = None, *args, **kwargs) -> str:
        """
        Translate text with automatic fallback to English.
        
        Args:
            text: Text to translate
            category: Optional category (GUI, Messages, Bookmarks, etc.)
            *args: Positional arguments for string formatting
            **kwargs: Keyword arguments for string formatting
        
        Returns:
            Translated text or original text if no translation found
        """
        translated = None
        
        # Try to find translation in current language
        if category:
            # Look in specific category first
            if category in self.translations and text in self.translations[category]:
                translated = self.translations[category][text]
        
        # If not found in category, search all categories
        if translated is None:
            for cat_name, cat_translations in self.translations.items():
                if text in cat_translations:
                    translated = cat_translations[text]
                    break
        
        # If not found and not already English, try English fallback
        if translated is None and self.current_language != "en":
            if category and category in self.english_fallback and text in self.english_fallback[category]:
                translated = self.english_fallback[category][text]
            else:
                # Search all English categories
                for cat_name, cat_translations in self.english_fallback.items():
                    if text in cat_translations:
                        translated = cat_translations[text]
                        break
        
        # If still not found, use original text
        if translated is None:
            translated = text
        
        # Apply formatting if arguments provided
        if args or kwargs:
            try:
                translated = translated.format(*args, **kwargs)
            except (KeyError, IndexError, ValueError):
                # If formatting fails, return unformatted text
                pass
        
        return translated
    
    def get_available_languages(self) -> list:
        """Get list of available language codes."""
        languages = []
        if os.path.exists(self.translations_dir):
            for file in os.listdir(self.translations_dir):
                if file.endswith('.json'):
                    languages.append(file[:-5])  # Remove .json extension
        return sorted(languages)
    
    def get_categories(self, language_code: str = None) -> list:
        """Get list of available categories."""
        if language_code is None:
            language_code = self.current_language
        
        if language_code == self.current_language:
            return list(self.translations.keys())
        else:
            # Load specific language to get categories
            translation_file = os.path.join(self.translations_dir, f"{language_code}.json")
            if os.path.exists(translation_file):
                try:
                    with open(translation_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict) and any(isinstance(v, dict) for v in data.values()):
                            return list(data.keys())
                except json.JSONDecodeError:
                    pass
        return []
    
    def add_translation(self, key: str, translation: str, category: str = "General", language_code: Optional[str] = None):
        """Add or update a translation in a specific category."""
        if language_code is None:
            language_code = self.current_language
        
        # Load the specific language file
        translation_file = os.path.join(self.translations_dir, f"{language_code}.json")
        translations = {}
        
        if os.path.exists(translation_file):
            try:
                with open(translation_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
            except json.JSONDecodeError:
                translations = {}
        
        # Ensure category exists
        if category not in translations:
            translations[category] = {}
        
        # Add the new translation
        translations[category][key] = translation
        
        # Save back to file
        with open(translation_file, 'w', encoding='utf-8') as f:
            json.dump(translations, f, indent=2, ensure_ascii=False, sort_keys=True)
        
        # Update current translations if it's the active language
        if language_code == self.current_language:
            if category not in self.translations:
                self.translations[category] = {}
            self.translations[category][key] = translation
    
    def get_missing_translations(self, target_language: str = None, category: str = None) -> Dict[str, list]:
        """Get missing translations organized by category."""
        if target_language is None:
            target_language = self.current_language
        
        if target_language == "en":
            return {}
        
        # Load target language
        translation_file = os.path.join(self.translations_dir, f"{target_language}.json")
        target_translations = {}
        
        if os.path.exists(translation_file):
            try:
                with open(translation_file, 'r', encoding='utf-8') as f:
                    target_translations = json.load(f)
            except json.JSONDecodeError:
                target_translations = {}
        
        # Find missing keys by category
        missing_by_category = {}
        
        categories_to_check = [category] if category else self.english_fallback.keys()
        
        for cat_name in categories_to_check:
            if cat_name not in self.english_fallback:
                continue
                
            missing = []
            english_cat = self.english_fallback[cat_name]
            target_cat = target_translations.get(cat_name, {})
            
            for key in english_cat.keys():
                if key not in target_cat or not target_cat[key].strip():
                    missing.append(key)
            
            if missing:
                missing_by_category[cat_name] = missing
        
        return missing_by_category


# Global translator instance
_translator = None

def get_translator() -> CategorizedTranslator:
    """Get the global translator instance."""
    global _translator
    if _translator is None:
        _translator = CategorizedTranslator()
    return _translator

def tr(text: str, category: str = None, *args, **kwargs) -> str:
    """
    Convenience function for translation with optional category.
    
    Examples:
        tr("Save Changes")  # Auto-detect category
        tr("Error", "Messages")  # Specific category
        tr("Could not create path folder:\\n{0}", "Messages", str(ex))  # With formatting
    """
    return get_translator().tr(text, category, *args, **kwargs)

def set_language(language_code: str):
    """Set the application language."""
    get_translator().set_language(language_code)

def get_available_languages() -> list:
    """Get available languages."""
    return get_translator().get_available_languages()

def get_categories() -> list:
    """Get available categories."""
    return get_translator().get_categories()