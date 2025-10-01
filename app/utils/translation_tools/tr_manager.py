#!/usr/bin/env python3
"""
Translation Manager for JsonLz4Tool

This script helps you manage translations:
- Extract translatable strings from source code
- Find missing translations
- Add new translations
- Validate translation files
"""

import os
import re
import json
import argparse
from pathlib import Path
from typing import Set, Dict, List


class TranslationManager:
    def __init__(self, project_root: str = "../../.."):
        self.project_root = Path(project_root)
        self.translations_dir = self.project_root / "assets" / "lang"
        self.app_dir = self.project_root / "app"
        
        # Ensure translations directory exists
        self.translations_dir.mkdir(exist_ok=True)
    
    def extract_strings_from_code(self) -> Set[str]:
        """Extract all tr() calls from Python source files."""
        translatable_strings = set()
        
        # Pattern to match tr ("string") calls
        tr_pattern = re.compile(r'tr\s*\(\s*["\']([^"\']+)["\']\s*[,\)]', re.MULTILINE)
        
        # Search in all Python files
        for py_file in self.app_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    matches = tr_pattern.findall(content)
                    translatable_strings.update(matches)
            except Exception as e:
                print(f"Error reading {py_file}: {e}")
        
        return translatable_strings
    
    def load_translation_file(self, language_code: str) -> Dict[str, str]:
        """Load a translation file."""
        translation_file = self.translations_dir / f"{language_code}.json"
        
        if not translation_file.exists():
            return {}
        
        try:
            with open(translation_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Invalid JSON in {translation_file}")
            return {}
    
    def save_translation_file(self, language_code: str, translations: Dict[str, str]):
        """Save a translation file."""
        translation_file = self.translations_dir / f"{language_code}.json"
        
        with open(translation_file, 'w', encoding='utf-8') as f:
            json.dump(translations, f, indent=2, ensure_ascii=False, sort_keys=True)
    
    def get_available_languages(self) -> List[str]:
        """Get list of available language codes."""
        languages = []
        for file in self.translations_dir.glob("*.json"):
            languages.append(file.stem)
        return sorted(languages)
    
    def update_english_base(self):
        """Update the English base translation file with strings from code."""
        print("Extracting translatable strings from source code...")
        code_strings = self.extract_strings_from_code()
        
        print(f"Found {len(code_strings)} translatable strings")
        
        # Load existing English translations
        english_translations = self.load_translation_file("en")
        
        # Add new strings (keeping existing translations)
        updated = False
        for string in code_strings:
            if string not in english_translations:
                english_translations[string] = string  # English uses the key as value
                updated = True
                print(f"Added new string: '{string}'")
        
        # Remove strings that are no longer in code
        code_strings_list = list(code_strings)
        for key in list(english_translations.keys()):
            if key not in code_strings:
                del english_translations[key]
                updated = True
                print(f"Removed obsolete string: '{key}'")
        
        if updated:
            self.save_translation_file("en", english_translations)
            print("Updated en.json")
        else:
            print("No changes needed for en.json")
        
        return english_translations
    
    def find_missing_translations(self, target_language: str) -> List[str]:
        """Find missing translations for a target language."""
        english_translations = self.load_translation_file("en")
        target_translations = self.load_translation_file(target_language)
        
        missing = []
        for key in english_translations.keys():
            if key not in target_translations or not target_translations[key].strip():
                missing.append(key)
        
        return missing
    
    def create_language_template(self, language_code: str):
        """Create a new language file template."""
        english_translations = self.load_translation_file("en")
        
        if not english_translations:
            print("Error: No English base file found. Run 'update-base' first.")
            return
        
        # Create template with empty translations
        template = {key: "" for key in english_translations.keys()}
        
        self.save_translation_file(language_code, template)
        print(f"Created template for {language_code}.json")
    
    def validate_translations(self):
        """Validate all translation files."""
        languages = self.get_available_languages()
        english_translations = self.load_translation_file("en")
        
        if not english_translations:
            print("Error: No English base file found.")
            return
        
        print(f"Validating translations for {len(languages)} languages...")
        
        for lang in languages:
            if lang == "en":
                continue
            
            translations = self.load_translation_file(lang)
            missing = self.find_missing_translations(lang)
            
            print(f"\n{lang}.json:")
            print(f"  Total keys: {len(english_translations)}")
            print(f"  Translated: {len(translations)}")
            print(f"  Missing: {len(missing)}")
            
            if missing:
                print("  Missing translations:")
                for key in missing[:5]:  # Show first 5
                    print(f"    - '{key}'")
                if len(missing) > 5:
                    print(f"    ... and {len(missing) - 5} more")
    
    def interactive_translate(self, language_code: str):
        """Interactive translation mode."""
        missing = self.find_missing_translations(language_code)
        
        if not missing:
            print(f"All translations for {language_code} are complete!")
            return
        
        translations = self.load_translation_file(language_code)
        
        print(f"Found {len(missing)} missing translations for {language_code}")
        print("Enter translations (press Enter to skip, 'q' to quit):\n")
        
        for i, key in enumerate(missing, 1):
            print(f"[{i}/{len(missing)}] English: '{key}'")
            translation = input(f"{language_code}: ").strip()
            
            if translation.lower() == 'q':
                break
            elif translation:
                translations[key] = translation
        
        self.save_translation_file(language_code, translations)
        print(f"Saved translations to {language_code}.json")


def main():
    parser = argparse.ArgumentParser(description="Translation Manager for JsonLz4Tool")
    parser.add_argument("command", choices=[
        "update-base", "validate", "missing", "create", "translate"
    ], help="Command to execute")
    parser.add_argument("--language", "-l", help="Language code (e.g., de, fr, es)")
    
    args = parser.parse_args()
    
    manager = TranslationManager()
    
    if args.command == "update-base":
        manager.update_english_base()
    
    elif args.command == "validate":
        manager.validate_translations()
    
    elif args.command == "missing":
        if not args.language:
            print("Error: --language required for 'missing' command")
            return
        
        missing = manager.find_missing_translations(args.language)
        if missing:
            print(f"Missing translations for {args.language}:")
            for key in missing:
                print(f"  - '{key}'")
        else:
            print(f"All translations for {args.language} are complete!")
    
    elif args.command == "create":
        if not args.language:
            print("Error: --language required for 'create' command")
            return
        
        manager.create_language_template(args.language)
    
    elif args.command == "translate":
        if not args.language:
            print("Error: --language required for 'translate' command")
            return
        
        manager.interactive_translate(args.language)


if __name__ == "__main__":
    main()