from enum import Enum
from typing import Dict, Any

class TranslationKey(str, Enum):
    # Discovery flow
    NO_INTERESTS_DEAD_END = "no_interests_dead_end"
    TELL_ME_MORE_ABOUT_TOPIC = "tell_me_more_about_topic"
    BRANCHING_QUESTION_DEFAULT = "branching_question_default"
    TRACK_DIRECTION_TITLE = "track_direction_title"
    TRACK_PREVIEW_TEXT = "track_preview_text"

TRANSLATIONS: Dict[str, Dict[TranslationKey, str]] = {
    "ru": {
        TranslationKey.NO_INTERESTS_DEAD_END: "Кажется, мы ничего не знаем о хобби. Давай попробуем найти зацепку: какая вещь в его/её доме самая любимая?",
        TranslationKey.TELL_ME_MORE_ABOUT_TOPIC: "Расскажите поподробнее про {topic} — что именно в этом увлекает?",
        TranslationKey.BRANCHING_QUESTION_DEFAULT: "Какое направление в теме '{topic}' вам ближе?",
        TranslationKey.TRACK_DIRECTION_TITLE: "Направление: {topic}",
        TranslationKey.TRACK_PREVIEW_TEXT: "Я изучил интересы в области {topic} и подготовил несколько идей.",
    },
    "en": {
        TranslationKey.NO_INTERESTS_DEAD_END: "It seems we don't know much about their hobbies. Let's find a clue: what is their favorite item at home?",
        TranslationKey.TELL_ME_MORE_ABOUT_TOPIC: "Tell me more about {topic} — what specifically is interesting about it?",
        TranslationKey.BRANCHING_QUESTION_DEFAULT: "Which area of '{topic}' do you prefer?",
        TranslationKey.TRACK_DIRECTION_TITLE: "Direction: {topic}",
        TranslationKey.TRACK_PREVIEW_TEXT: "I've explored interests in {topic} and prepared some ideas.",
    }
}

class I18nService:
    def translate(self, key: TranslationKey, language: str, **kwargs) -> str:
        lang = language.lower()
        if lang not in TRANSLATIONS:
            lang = "ru" # Default
            
        text = TRANSLATIONS[lang].get(key, str(key))
        return text.format(**kwargs)

# Singleton instance
i18n = I18nService()
