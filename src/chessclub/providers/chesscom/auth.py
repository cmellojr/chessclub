"""Chess.com authentication providers.

Two implementations are defined here:

* :class:`ChessComCookieAuth` — the current working approach.  Resolves
  ``ACCESS_TOKEN`` and ``PHPSESSID`` session cookies from constructor
  arguments, environment variables, or the local credentials file.

* :class:`ChessComOAuth` — **not yet implemented**.  Placeholder for the
  future OAuth 2.0 flow once Chess.com grants application access.
  See: https://www.chess.com/clubs/forum/view/guide-applying-for-oauth-access
"""

import os

from chessclub.auth.credentials import load as _load_stored
from chessclub.auth.interfaces import AuthCredentials, AuthProvider
from chessclub.core.exceptions import AuthenticationRequiredError

# Chess.com-specific cookie names — kept here so the provider (client.py)
# never has to know about them.
_COOKIE_ACCESS_TOKEN = "ACCESS_TOKEN"
_COOKIE_PHPSESSID = "PHPSESSID"

_ENV_ACCESS_TOKEN = "CHESSCOM_ACCESS_TOKEN"
_ENV_PHPSESSID = "CHESSCOM_PHPSESSID"


class ChessComCookieAuth(AuthProvider):
    """Resolves Chess.com session cookies from multiple sources.

    Resolution order (first match wins):

    1. Values passed directly to the constructor.
    2. ``CHESSCOM_ACCESS_TOKEN`` and ``CHESSCOM_PHPSESSID`` environment
       variables.
    3. Credentials stored in ``~/.config/chessclub/credentials.json``.

    Attributes:
        ACCESS_TOKEN: Chess.com session token (~24 h expiry).
        PHPSESSID: PHP session identifier.
    """

    def __init__(
        self,
        access_token: str | None = None,
        phpsessid: str | None = None,
    ):
        """Initialise the auth provider.

        Args:
            access_token: Chess.com ACCESS_TOKEN cookie value.  When
                provided together with ``phpsessid``, env vars and the
                stored file are skipped.
            phpsessid: Chess.com PHPSESSID cookie value.
        """
        self._access_token = access_token
        self._phpsessid = phpsessid

    # -------------------------
    # AuthProvider interface
    # -------------------------

    def get_credentials(self) -> AuthCredentials:
        """Return Chess.com session cookies as generic credentials.

        Returns:
            An :class:`AuthCredentials` instance with the resolved cookies.

        Raises:
            AuthenticationRequiredError: If credentials cannot be found in
                any configured source.
        """
        token, sessid = self._resolve()
        if token is None or sessid is None:
            raise AuthenticationRequiredError(
                "Chess.com credentials not found. "
                "Run 'chessclub auth setup' to configure them."
            )
        return AuthCredentials(
            cookies={
                _COOKIE_ACCESS_TOKEN: token,
                _COOKIE_PHPSESSID: sessid,
            }
        )

    def is_authenticated(self) -> bool:
        """Return ``True`` if Chess.com credentials are available.

        Returns:
            ``True`` when both ACCESS_TOKEN and PHPSESSID are resolvable
            from any configured source.
        """
        token, sessid = self._resolve()
        return token is not None and sessid is not None

    # -------------------------
    # Internal helpers
    # -------------------------

    def _resolve(self) -> tuple[str | None, str | None]:
        """Resolve token and session ID from all available sources.

        Returns:
            A ``(access_token, phpsessid)`` tuple.  Either element is
            ``None`` if it could not be resolved.
        """
        # 1. Constructor values (highest priority)
        if self._access_token and self._phpsessid:
            return self._access_token, self._phpsessid

        # 2. Environment variables
        token = os.getenv(_ENV_ACCESS_TOKEN)
        sessid = os.getenv(_ENV_PHPSESSID)
        if token and sessid:
            return token, sessid

        # 3. Credentials file
        stored = _load_stored()
        token = stored.get("access_token")
        sessid = stored.get("phpsessid")
        if token and sessid:
            return token, sessid

        return None, None

    def credential_source(self) -> str:
        """Return a human-readable description of where credentials came from.

        Useful for the ``auth status`` CLI command.

        Returns:
            A string such as ``"environment variables"`` or the path to the
            credentials file.
        """
        if self._access_token and self._phpsessid:
            return "constructor arguments"
        if os.getenv(_ENV_ACCESS_TOKEN):
            return "environment variables"
        from chessclub.auth.credentials import credentials_path
        return str(credentials_path())


# ---------------------------------------------------------------------------
# OAuth 2.0 — future implementation
# ---------------------------------------------------------------------------


class ChessComOAuth(AuthProvider):
    """OAuth 2.0 authentication for Chess.com.

    Chess.com provides an OAuth 2.0 flow for approved applications.
    Developers must apply for access before it can be used.

    References:
        https://www.chess.com/clubs/forum/view/guide-applying-for-oauth-access

    Note:
        This class is a **placeholder**.  OAuth 2.0 support is not yet
        implemented.  Instantiating it will raise ``NotImplementedError``.
        The class exists to document the intended future interface and to
        allow type-checked dependency injection once it is built.

    Future interface (subject to change)::

        auth = ChessComOAuth(
            client_id="<your-client-id>",
            client_secret="<your-client-secret>",
        )
        provider = ChessComClient(auth=auth)
    """

    def __init__(self, client_id: str, client_secret: str):
        """Initialise the OAuth provider.

        Args:
            client_id: The OAuth 2.0 client ID issued by Chess.com.
            client_secret: The OAuth 2.0 client secret issued by Chess.com.

        Raises:
            NotImplementedError: Always — this class is not yet implemented.
        """
        raise NotImplementedError(
            "Chess.com OAuth 2.0 is not yet implemented. "
            "Use ChessComCookieAuth in the meantime."
        )

    def get_credentials(self) -> AuthCredentials:
        raise NotImplementedError

    def is_authenticated(self) -> bool:
        raise NotImplementedError
