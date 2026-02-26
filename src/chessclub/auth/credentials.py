"""Persistent storage for Chess.com credentials.

Two separate files are managed here:

* ``credentials.json`` — cookie-based session credentials (``ACCESS_TOKEN``
  and ``PHPSESSID``).  Written by ``auth setup``.
* ``oauth_token.json`` — OAuth 2.0 PKCE tokens (``access_token``,
  ``refresh_token``, ``expires_at``).  Written by ``auth login``.

Both files are stored under ``~/.config/chessclub/`` with permissions
restricted to the owner (0o600).
"""

import json
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "chessclub"
_CREDENTIALS_FILE = _CONFIG_DIR / "credentials.json"
_OAUTH_TOKEN_FILE = _CONFIG_DIR / "oauth_token.json"


# ---------------------------------------------------------------------------
# Cookie-based credentials (ACCESS_TOKEN + PHPSESSID)
# ---------------------------------------------------------------------------


def save(access_token: str, phpsessid: str) -> None:
    """Persist cookie credentials to the config file.

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
    """Load cookie credentials from the config file.

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
    """Remove the cookie credentials file.

    Returns:
        ``True`` if the file was deleted, ``False`` if it did not exist.
    """
    if _CREDENTIALS_FILE.exists():
        _CREDENTIALS_FILE.unlink()
        return True
    return False


def credentials_path() -> Path:
    """Return the path to the cookie credentials file.

    Returns:
        A :class:`pathlib.Path` pointing to the credentials JSON file.
    """
    return _CREDENTIALS_FILE


# ---------------------------------------------------------------------------
# OAuth 2.0 token storage
# ---------------------------------------------------------------------------


def save_oauth_token(
    access_token: str,
    refresh_token: str | None,
    expires_at: float,
    scope: str | None = None,
) -> None:
    """Persist an OAuth 2.0 token set to the config file.

    Creates the config directory if it does not already exist and restricts
    file permissions to the owner only.

    Args:
        access_token: The OAuth Bearer access token.
        refresh_token: The refresh token, or ``None`` if not provided.
        expires_at: Unix timestamp at which the access token expires.
        scope: Space-separated OAuth scopes granted, or ``None``.
    """
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _OAUTH_TOKEN_FILE.write_text(
        json.dumps(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "scope": scope,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _OAUTH_TOKEN_FILE.chmod(0o600)


def load_oauth_token() -> dict | None:
    """Load an OAuth 2.0 token set from the config file.

    Returns:
        A dictionary with ``access_token``, ``refresh_token``,
        ``expires_at``, and ``scope`` keys, or ``None`` if the file does
        not exist or cannot be parsed.
    """
    if not _OAUTH_TOKEN_FILE.exists():
        return None
    try:
        return json.loads(_OAUTH_TOKEN_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def clear_oauth_token() -> bool:
    """Remove the OAuth token file.

    Returns:
        ``True`` if the file was deleted, ``False`` if it did not exist.
    """
    if _OAUTH_TOKEN_FILE.exists():
        _OAUTH_TOKEN_FILE.unlink()
        return True
    return False


def oauth_token_path() -> Path:
    """Return the path to the OAuth token file.

    Returns:
        A :class:`pathlib.Path` pointing to the OAuth token JSON file.
    """
    return _OAUTH_TOKEN_FILE
