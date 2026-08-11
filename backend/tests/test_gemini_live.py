from app.services.gemini_live import (
    build_audio_input,
    build_setup,
    build_text_input,
    classify_gemini_error,
    translate_server_message,
)


def test_setup_requests_native_audio_transcripts_and_session_management():
    message = build_setup("gemini-3.1-flash-live-preview", "Kore")
    setup = message["setup"]
    assert setup["model"] == "models/gemini-3.1-flash-live-preview"
    assert "responseModalities" not in setup
    assert setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert setup["inputAudioTranscription"] == {}
    assert setup["outputAudioTranscription"] == {}
    assert setup["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Kore"
    assert setup["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert setup["realtimeInputConfig"] == {
        "automaticActivityDetection": {
            "disabled": False,
            "startOfSpeechSensitivity": "START_SENSITIVITY_LOW",
            "endOfSpeechSensitivity": "END_SENSITIVITY_LOW",
            "prefixPaddingMs": 100,
            "silenceDurationMs": 700,
        }
    }
    assert setup["contextWindowCompression"] == {"slidingWindow": {}}
    assert setup["sessionResumption"] == {}


def test_input_messages_use_realtime_pcm_and_text_shapes():
    assert build_audio_input("AAA=") == {
        "realtimeInput": {
            "audio": {"data": "AAA=", "mimeType": "audio/pcm;rate=16000"}
        }
    }
    assert build_text_input(" hello ") == {"realtimeInput": {"text": "hello"}}


def test_translator_processes_every_part_and_server_signal():
    message = {
        "serverContent": {
            "modelTurn": {"parts": [
                {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": "AAA="}},
                {"text": "ignored native text"},
            ]},
            "inputTranscription": {"text": "Hello"},
            "outputTranscription": {"text": "Hi there"},
            "generationComplete": True,
        },
        "sessionResumptionUpdate": {"resumable": True, "newHandle": "resume-1"},
    }
    assert translate_server_message(message) == [
        {"type": "audio", "data": "AAA="},
        {"type": "input_transcript_delta", "text": "Hello"},
        {"type": "output_transcript_delta", "text": "Hi there"},
        {"type": "response_done"},
        {"type": "resumption", "handle": "resume-1"},
    ]


def test_translator_reports_interruption_and_goaway_without_generic_error():
    assert translate_server_message({"serverContent": {"interrupted": True}}) == [
        {"type": "interrupted"}
    ]
    assert translate_server_message({"goAway": {"timeLeft": "5s"}}) == [
        {"type": "go_away", "time_left": "5s"}
    ]


def test_error_classification_only_falls_back_for_retryable_provider_failures():
    assert classify_gemini_error(503, "UNAVAILABLE") == "retryable"
    assert classify_gemini_error(429, "RESOURCE_EXHAUSTED") == "retryable"
    assert classify_gemini_error(401, "UNAUTHENTICATED") == "configuration"
    assert classify_gemini_error(400, "INVALID_ARGUMENT") == "configuration"
