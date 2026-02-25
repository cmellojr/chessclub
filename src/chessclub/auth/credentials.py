"""Persistent storage for Chess.com session credentials.

Credentials are written to ``~/.config/chessclub/credentials.json`` with
permissions restricted to the owner (0o600).  Environment variables always
take precedence over stored values.
"""

import json
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "chessclub"
_CREDENTIALS_FILE = _CONFIG_DIR / "credentials.json"


def save(access_token: str, phpsessid: str) -> None:
    """Persist credentials to the config file.

    Creates the config directory if it does not already exist and restricts
    file permissions to the owner only.

    Args:
        access_token: The Chess.com ACCESS_TOKEN cookie value.
        phpsessid: The Chess.com PHPSESSID cookie value.
    """
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CREDENTIALS_FILE.write_text(
        json.dumps(
            {"access_token": access_token, "phpsessid": phpsessid},
            indent=2,
        ),
        encoding="utf-8",
    )
    _CREDENTIALS_FILE.chmod(0o600)


def load() -> dict[str, str]:
    """Load credentials from the config file.

    Returns:
        A dictionary with ``access_token`` and ``phpsessid`` keys, or an
        empty dictionary if no credentials file exists or it cannot be parsed.
    """
    if not _CREDENTIALS_FILE.exists():
        return {}
    try:
        return json.loads(_CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def clear() -> bool:
    """Remove the credentials file.

    Returns:
        ``True`` if the file was deleted, ``False`` if it did not exist.
    """
    if _CREDENTIALS_FILE.exists():
        _CREDENTIALS_FILE.unlink()
        return True
    return False


def credentials_path() -> Path:
    """Return the path to the credentials file.

    Returns:
        A :class:`pathlib.Path` pointing to the credentials JSON file.
    """
    return _CREDENTIALS_FILE
