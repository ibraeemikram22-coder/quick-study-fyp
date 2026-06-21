import os

_tool = None


def get_tool():
    """Load LanguageTool when grammar API is called (not at app startup)."""
    global _tool
    if _tool is not None:
        return _tool

    try:
        import language_tool_python
    except ImportError as exc:
        raise RuntimeError(
            "Grammar module not installed. Run: pip install language-tool-python"
        ) from exc

    if os.getenv("PYTHONANYWHERE_SITE") or os.getenv("GRAMMAR_USE_PUBLIC_API", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        _tool = language_tool_python.LanguageToolPublicAPI("en-US")
        return _tool

    java_home = os.getenv("JAVA_HOME")
    if java_home:
        os.environ["PATH"] = os.path.join(java_home, "bin") + os.pathsep + os.environ.get("PATH", "")

    try:
        _tool = language_tool_python.LanguageTool("en-US")
    except Exception:
        _tool = language_tool_python.LanguageToolPublicAPI("en-US")
    return _tool
