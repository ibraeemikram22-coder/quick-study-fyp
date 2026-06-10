import os

_tool = None


def get_tool():
    """Load LanguageTool only when grammar API is called (not at app startup)."""
    global _tool
    if _tool is not None:
        return _tool

    try:
        import language_tool_python
    except ImportError as exc:
        raise RuntimeError(
            "Grammar module not installed. Run: "
            "venv\\Scripts\\python.exe -m pip install language-tool-python"
        ) from exc

    java_home = os.getenv("JAVA_HOME")
    if java_home:
        os.environ["PATH"] = os.path.join(java_home, "bin") + os.pathsep + os.environ.get("PATH", "")

    _tool = language_tool_python.LanguageTool("en-US")
    return _tool
