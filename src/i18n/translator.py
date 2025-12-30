class Translator:
    def __init__(self, translations: dict, default_language: str = "ru") -> None:
        self.translations = translations
        self.default_language = default_language
        self.languages: tuple[str, ...] = tuple(translations.keys())

    def get_text(self, text: str, language: str) -> str:
        try:
            return self.translations[language][text]
        except KeyError:
            return self.translations.get(self.default_language, {}).get(text, text)
