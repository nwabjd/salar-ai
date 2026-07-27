import asyncio
import base64
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from ..models import User
from ..security import get_current_user

router = APIRouter(tags=["stt"])
log = logging.getLogger(__name__)

_whisper_model = None


@router.post("/api/stt")
async def speech_to_text(
    request: Request,
    file: UploadFile = File(...),
    fast: bool = Query(default=False),
    user: User = Depends(get_current_user),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio")

    if not fast:
        gemini = getattr(request.app.state.coordinator, "gemini", None)
        if gemini:
            try:
                text = await gemini.stt(audio_bytes, file.content_type or "audio/webm")
                return JSONResponse({"text": text})
            except Exception as e:
                log.warning("Gemini STT failed, falling back to local Whisper: %s", e)

    text = await asyncio.to_thread(_whisper_transcribe, audio_bytes, file.content_type or "audio/webm")
    return JSONResponse({"text": text})


def _whisper_transcribe(audio_bytes: bytes, content_type: str) -> str:
    global _whisper_model

    suffix = ".webm"
    if "mp4" in content_type:
        suffix = ".mp4"
    elif "wav" in content_type:
        suffix = ".wav"
    elif "ogg" in content_type:
        suffix = ".ogg"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(audio_bytes)
    tmp.close()

    wav_path = None
    try:
        from pydub import AudioSegment
        sound = AudioSegment.from_file(tmp.name)
        sound = sound.set_frame_rate(16000).set_channels(1)

        wav_path = tmp.name + ".wav"
        sound.export(wav_path, format="wav")

        import numpy as np
        sound_raw = AudioSegment.from_wav(wav_path)
        samples = np.array(sound_raw.get_array_of_samples(), dtype=np.float32)
        samples = samples / 32768.0

        if _whisper_model is None:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            log.info("Whisper tiny model loaded on CPU")

        segments, _ = _whisper_model.transcribe(samples, beam_size=1, language=None)
        return " ".join(seg.text.strip() for seg in segments)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        if wav_path:
            try:
                os.unlink(wav_path)
            except OSError:
                pass
