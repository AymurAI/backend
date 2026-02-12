from contextlib import suppress
from hashlib import blake2b
from pathlib import Path
from typing import Any

from aymurai.audio.asr_client import transcribe_audio_path
from aymurai.logger import get_logger
from aymurai.settings import settings
from aymurai.text.extractors.base import BaseExtractor, InvalidFile, register_extractor
from aymurai.text.extractors.utils import normalize_text
from aymurai.utils.cache import cache_load, cache_save, get_cache_key

logger = get_logger(__file__)


@register_extractor
class AudioExtractor(BaseExtractor):
    extensions = {"wav", "mp3", "m4a", "flac", "ogg", "webm", "aac"}

    def extract(
        self,
        path: Path,
        *,
        use_cache: bool = True,
        **_: Any,
    ) -> str:
        file_path = self.ensure_file(path)

        ws_uri = settings.TRANSCRIBE_WS_URI
        if not ws_uri:
            raise InvalidFile("TRANSCRIBE_WS_URI is not configured")

        cache_key = self._cache_key(file_path) if use_cache else None
        if use_cache and cache_key:
            cached_text = cache_load(cache_key)
            if cached_text is not None:
                logger.debug("Audio cache hit for %s", file_path)
                return cached_text

        try:
            status = transcribe_audio_path(file_path, ws_uri=ws_uri)
        except Exception as exc:
            raise InvalidFile(str(exc)) from exc

        if not status or not status.lines:
            return ""

        lines = [line.text.strip() for line in status.lines if line.text.strip()]
        text = normalize_text("\n".join(lines))

        if use_cache and cache_key:
            cache_save(text, key=cache_key)
            logger.debug("Audio cache stored for %s", file_path)

        return text

    @staticmethod
    def _cache_key(file_path: Path) -> str | None:
        with suppress(OSError):
            hasher = blake2b(digest_size=32)
            with file_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    hasher.update(chunk)
            fingerprint = hasher.hexdigest()
            stat = file_path.stat()

            return get_cache_key(
                fingerprint,
                context={
                    "component": "audio-extractor",
                    "size": stat.st_size,
                },
            )
