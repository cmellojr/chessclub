"""Lichess API token authentication."""

import json
import os
from pathlib import Path

from chessclub.auth.interfaces import AuthCredentials, AuthProvider
from chessclub.core.exceptions import AuthenticationRequiredError


class LichessTokenAuth(AuthProvider):
    """Authenticates against Lichess using a personal API token.

    Token resolution order:

    1. Constructor argument.
    2. ``LICHESS_API_TOKEN`` environment variable.
    3. ``~/.config/chessclub/lichess_token.json`` (mode 0o600).

    A personal API token can be generated at
    https://lichess.org/account/oauth/token.  Most Lichess endpoints are
    public and work without any token; the token is only required for
    private teams or write operations.
    """

    _CONFIG_FILE = Path.home() / ".config" / "chessclub" / "lichess_token.json"
    _ENV_VAR = "LICHESS_API_TOKEN"

    def __init__(self, token: str | None = None):
        """Initialise with an optional explicit token.

        Args:
            token: Lichess personal API token.  Falls back to the
                environment variable and config file when ``None``.
        """
        self._token: str | None = (
            token or os.getenv(self._ENV_VAR) or self._load_from_file()
        )

    # ------------------------------------------------------------------
    # AuthProvider interface
    # ------------------------------------------------------------------

    def get_credentials(self) -> AuthCredentials:
        """Return Bearer token credentials.

        Returns:
            AuthCredentials with the Authorization header set.

        Raises:
            AuthenticationRequiredError: If no token is configured.
        """
        if not self._token:
            raise AuthenticationRequiredError(
                "Lichess API token not configured. "
                "Set LICHESS_API_TOKEN or save a token with "
                "LichessTokenAuth.save_token(token)."
            )
        return AuthCredentials(
            headers={"Authorization": f"Bearer {self._token}"}
        )

    def is_authenticated(self) -> bool:
        """Return True if a token is available.

        Returns:
            True when a token was resolved from any source.
        """
        return bool(self._token)

    # ------------------------------------------------------------------
    # Token persistence
    # ------------------------------------------------------------------

    @classmethod
    def save_token(cls, token: str) -> None:
        """Persist a token to disk with restricted permissions.

        Args:
            token: Lichess personal API token to save.
        """
        cls._CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls._CONFIG_FILE.write_text(json.dumps({"token": token}, indent=2))
        cls._CONFIG_FILE.chmod(0o600)

    def _load_from_file(self) -> str | None:
        try:
            data = json.loads(self._CONFIG_FILE.read_text())
            return data.get("token")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None
