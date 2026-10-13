"""Pure SSML construction for spoken commentary: one neural voice per supported language, escaped text, size cap.

Voices are chosen for a broadcast delivery in each market the app suggests; unsupported languages have no voice,
so callers can fall back to on-device speech. Text is XML-escaped and truncated so no input can break the markup.
"""

from xml.sax.saxutils import escape

MAX_SPEECH_CHARS: int = 400
NEURAL_VOICES: dict[str, str] = {
    "en": "en-GB-RyanNeural", "es": "es-ES-AlvaroNeural", "fr": "fr-FR-HenriNeural", "de": "de-DE-ConradNeural",
    "pt": "pt-BR-AntonioNeural", "ar": "ar-SA-HamedNeural", "tr": "tr-TR-AhmetNeural", "ja": "ja-JP-KeitaNeural",
    "hi": "hi-IN-MadhurNeural", "sw": "sw-KE-RafikiNeural",
}
SPEAKING_RATE: str = "+8%"


def voice_for(language: str) -> str | None:
    """The neural voice for a two-letter language code, or None when the language has no configured voice."""
    return NEURAL_VOICES.get(language.lower())


def build_ssml(text: str, voice: str) -> str:
    """SSML speaking text (truncated to MAX_SPEECH_CHARS) with the given voice at a brisk broadcast pace."""
    locale = voice.rsplit("-", 1)[0]
    body = escape(text.strip()[:MAX_SPEECH_CHARS])
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{locale}">'
            f'<voice name="{voice}"><prosody rate="{SPEAKING_RATE}">{body}</prosody></voice></speak>')
