_model = None
_whisper_ok = None


def whisper_available():
    global _whisper_ok
    if _whisper_ok is not None:
        return _whisper_ok
    try:
        import whisper  # noqa: F401
        import torch  # noqa: F401
        _whisper_ok = True
    except Exception:
        _whisper_ok = False
    return _whisper_ok


def get_transcript(audio_path):
    global _model
    if _model is None:
        try:
            import whisper
        except ImportError as exc:
            raise RuntimeError(
                "Whisper not installed. Run: python -m pip install openai-whisper torch"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Whisper could not load ({exc}). Try: python -m pip install --upgrade torch openai-whisper"
            ) from exc
        _model = whisper.load_model("base")
    result = _model.transcribe(audio_path)
    return result.get("text") or ""
