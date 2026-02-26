"""Chess.com authentication providers.

Two implementations are defined here:

* :class:`ChessComCookieAuth` — the current working approach.  Resolves
  ``ACCESS_TOKEN`` and ``PHPSESSID`` session cookies from constructor
  arguments, environment variables, or the local credentials file.

* :class:`ChessComOAuth` — OAuth 2.0 PKCE + Loopback Local Server flow.
  Requires a ``client_id`` issued by Chess.com (apply at the link below).
  Until Chess.com grants application access, gate on the ``CHESSCOM_CLIENT_ID``
  environment variable.
  See: https://www.chess.com/clubs/forum/view/guide-applying-for-oauth-access
"""

import base64
import hashlib
import http.server
import os
import secrets
import time
import urllib.parse
import webbrowser
from threading import Event

import requests

from chessclub.auth.credentials import (
    load as _load_stored,
    load_oauth_token as _load_oauth_token,
    save_oauth_token as _save_oauth_token,
)
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
# OAuth 2.0 — PKCE + Loopback Local Server
# ---------------------------------------------------------------------------

_OAUTH_AUTH_URL = "https://oauth.chess.com/authorize"
_OAUTH_TOKEN_URL = "https://oauth.chess.com/token"

# How many seconds before actual expiry to treat the token as expired,
# preventing requests failing due to clock skew or network latency.
_EXPIRY_BUFFER_SECONDS = 60


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the OAuth authorization code.

    The handler stores the received ``code`` on the server instance and
    signals the waiting thread via ``_done`` so the login flow can proceed.
    """

    def do_GET(self):  # noqa: N802 — method name required by http.server
        """Handle the browser redirect from Chess.com."""
        params = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query
        )
        self.server.auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Login successful.</h2>"
            b"<p>You can close this tab and return to the terminal.</p>"
            b"</body></html>"
        )
        self.server._done.set()

    def log_message(self, format, *args):  # noqa: A002
        """Suppress the default request log to keep the terminal clean."""


class ChessComOAuth(AuthProvider):
    """OAuth 2.0 PKCE authentication for Chess.com.

    Implements the Authorization Code + PKCE flow with a Loopback Local
    Server redirect URI (RFC 8252), matching the pattern used by ``gcloud``,
    ``aws-cli``, and ``gh``.

    No ``client_secret`` is required — PKCE replaces it for public native
    applications.

    Usage::

        auth = ChessComOAuth(client_id="<your-client-id>")
        provider = ChessComClient(user_agent="...", auth=auth)

    To initiate the login flow from the CLI::

        ChessComOAuth.run_login_flow(client_id="<your-client-id>")

    References:
        https://www.chess.com/clubs/forum/view/guide-applying-for-oauth-access
        https://www.rfc-editor.org/rfc/rfc8252  (OAuth 2.0 for Native Apps)
        https://www.rfc-editor.org/rfc/rfc7636  (PKCE)
    """

    def __init__(self, client_id: str):
        """Initialise the OAuth provider.

        Args:
            client_id: The OAuth 2.0 client ID issued by Chess.com.
        """
        self._client_id = client_id
        self._token: dict | None = _load_oauth_token()

    # -------------------------
    # AuthProvider interface
    # -------------------------

    def get_credentials(self) -> AuthCredentials:
        """Return a Bearer token, refreshing it automatically if expired.

        Returns:
            An :class:`AuthCredentials` instance with an ``Authorization``
            header containing the current Bearer token.

        Raises:
            AuthenticationRequiredError: If no token is stored or the token
                cannot be refreshed (e.g. refresh token is absent or invalid).
        """
        if self._token is None:
            raise AuthenticationRequiredError(
                "No OAuth token found. Run 'chessclub auth login'."
            )

        if self._is_expired():
            if self._token.get("refresh_token"):
                self._refresh()
            else:
                raise AuthenticationRequiredError(
                    "OAuth token expired and no refresh token is available. "
                    "Run 'chessclub auth login' to re-authenticate."
                )

        return AuthCredentials(
            headers={"Authorization": f"Bearer {self._token['access_token']}"}
        )

    def is_authenticated(self) -> bool:
        """Return ``True`` if a valid or refreshable token is stored.

        Returns:
            ``True`` when an access token is present and either unexpired
            or refreshable via a stored refresh token.
        """
        if self._token is None:
            return False
        if not self._is_expired():
            return True
        return bool(self._token.get("refresh_token"))

    # -------------------------
    # Static login flow
    # -------------------------

    @staticmethod
    def run_login_flow(client_id: str) -> None:
        """Run the PKCE + Loopback Local Server authorization flow.

        Starts a temporary HTTP server on a random loopback port, opens the
        user's default browser to the Chess.com authorization page, waits for
        the redirect, exchanges the authorization code for tokens, and persists
        the token set to disk.

        Args:
            client_id: The OAuth 2.0 client ID issued by Chess.com.

        Raises:
            requests.RequestException: If the token exchange HTTP request
                fails.
        """
        # Step 1 — Generate PKCE values.
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = (
            base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        )

        # Step 2 — Start a loopback server on a random OS-assigned port.
        server = http.server.HTTPServer(("127.0.0.1", 0), _CallbackHandler)
        server._done = Event()
        server.auth_code = None
        port = server.server_address[1]
        redirect_uri = f"http://127.0.0.1:{port}/callback"

        # Step 3 — Build authorization URL.
        params = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        auth_url = f"{_OAUTH_AUTH_URL}?{params}"

        # Step 4 — Open browser and wait for the redirect.
        print(f"\nOpening browser for Chess.com login…\n{auth_url}\n")
        webbrowser.open(auth_url)

        server.handle_request()  # blocks until _CallbackHandler.do_GET fires
        server.server_close()

        auth_code = server.auth_code
        if not auth_code:
            raise AuthenticationRequiredError(
                "Authorization code was not received from Chess.com."
            )

        # Step 5 — Exchange code for tokens.
        response = requests.post(
            _OAUTH_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": code_verifier,
            },
            timeout=30,
        )
        response.raise_for_status()
        token_data = response.json()

        expires_at = time.time() + token_data.get("expires_in", 3600)
        _save_oauth_token(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
            scope=token_data.get("scope"),
        )

    # -------------------------
    # Internal helpers
    # -------------------------

    def _is_expired(self) -> bool:
        """Return ``True`` if the access token has expired (or is about to).

        Returns:
            ``True`` when the stored ``expires_at`` timestamp is within
            :data:`_EXPIRY_BUFFER_SECONDS` of the current time.
        """
        if self._token is None:
            return True
        expires_at = self._token.get("expires_at", 0.0)
        return time.time() >= expires_at - _EXPIRY_BUFFER_SECONDS

    def _refresh(self) -> None:
        """Exchange the stored refresh token for a new access token.

        Updates ``self._token`` in memory and persists the new token to disk.

        Raises:
            AuthenticationRequiredError: If the refresh request fails.
        """
        response = requests.post(
            _OAUTH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._token["refresh_token"],
                "client_id": self._client_id,
            },
            timeout=30,
        )
        if not response.ok:
            raise AuthenticationRequiredError(
                "OAuth token refresh failed. "
                "Run 'chessclub auth login' to re-authenticate."
            )
        token_data = response.json()
        expires_at = time.time() + token_data.get("expires_in", 3600)
        self._token = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get(
                "refresh_token", self._token.get("refresh_token")
            ),
            "expires_at": expires_at,
            "scope": token_data.get("scope", self._token.get("scope")),
        }
        _save_oauth_token(
            access_token=self._token["access_token"],
            refresh_token=self._token["refresh_token"],
            expires_at=expires_at,
            scope=self._token["scope"],
        )
