from typing import Callable

from .locales import translations
from .translator import Translator

translator = Translator(translations, "ru")
translate: Callable[[str, str], str] = translator.get_text

__all__ = ["translator", "translate"]
