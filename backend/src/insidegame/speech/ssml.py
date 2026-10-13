"""Pure SSML construction for spoken commentary: one neural voice per supported language, escaped text, size cap.

Voices are chosen for a broadcast delivery in each market the app suggests; unsupported languages have no voice,
so callers can fall back to on-device speech. Pace follows the replay speed (natural at real time, quicker when the
match is sped up) and lifts with the line's intensity, mostly through pace so the voice stays natural. Text is
XML-escaped and truncated so no input can break the markup.
"""

import math
from xml.sax.saxutils import escape

from insidegame.domain.enums import Intensity

MAX_SPEECH_CHARS: int = 400
NEURAL_VOICES: dict[str, str] = {
    "en": "en-GB-RyanNeural", "es": "es-ES-AlvaroNeural", "fr": "fr-FR-HenriNeural", "de": "de-DE-ConradNeural",
    "pt": "pt-BR-AntonioNeural", "ar": "ar-SA-HamedNeural", "tr": "tr-TR-AhmetNeural", "ja": "ja-JP-KeitaNeural",
    "hi": "hi-IN-MadhurNeural", "sw": "sw-KE-RafikiNeural",
}
REAL_TIME_PACE: float = 1.0
PACE_PER_DECADE: float = 0.1
MAX_PACE: float = 1.25
PERCENT: float = 100.0
INTENSITY_PACE: dict[Intensity, float] = {Intensity.NORMAL: 1.0, Intensity.RAISED: 1.06, Intensity.PEAK: 1.12}
INTENSITY_PITCH: dict[Intensity, str] = {Intensity.NORMAL: "+0%", Intensity.RAISED: "+3%", Intensity.PEAK: "+6%"}


def pace_for_speed(speed: float) -> float:
    """Base speaking pace for a replay speed: 1.0 at real time, plus 0.1 per tenfold speed-up, capped at 1.25."""
    return min(max(REAL_TIME_PACE + PACE_PER_DECADE * math.log10(max(speed, 1.0)), REAL_TIME_PACE), MAX_PACE)


def voice_for(language: str) -> str | None:
    """The neural voice for a two-letter language code, or None when the language has no configured voice."""
    return NEURAL_VOICES.get(language.lower())


def build_ssml(text: str, voice: str, intensity: Intensity = Intensity.NORMAL, pace: float = REAL_TIME_PACE) -> str:
    """SSML speaking text (truncated to MAX_SPEECH_CHARS) with the voice.

    Defaults: intensity NORMAL and pace REAL_TIME_PACE (1.0, natural speed); see pace_for_speed for replays.
    """
    locale = voice.rsplit("-", 1)[0]
    body = escape(text.strip()[:MAX_SPEECH_CHARS])
    rate = f"{round((pace * INTENSITY_PACE[intensity] - 1.0) * PERCENT):+d}%"
    pitch = INTENSITY_PITCH[intensity]
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{locale}">'
            f'<voice name="{voice}"><prosody rate="{rate}" pitch="{pitch}">{body}</prosody></voice></speak>')
