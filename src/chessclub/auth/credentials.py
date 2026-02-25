import json
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "chessclub"
_CREDENTIALS_FILE = _CONFIG_DIR / "credentials.json"


def save(access_token: str, phpsessid: str) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CREDENTIALS_FILE.write_text(
        json.dumps({"access_token": access_token, "phpsessid": phpsessid}, indent=2),
        encoding="utf-8",
    )
    _CREDENTIALS_FILE.chmod(0o600)


def load() -> dict[str, str]:
    if not _CREDENTIALS_FILE.exists():
        return {}
    try:
        return json.loads(_CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def clear() -> bool:
    if _CREDENTIALS_FILE.exists():
        _CREDENTIALS_FILE.unlink()
        return True
    return False


def credentials_path() -> Path:
    return _CREDENTIALS_FILE
