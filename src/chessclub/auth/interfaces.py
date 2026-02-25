"""Abstract interfaces for the authentication layer.

This module defines the contracts that any authentication strategy must
implement.  It is intentionally free of platform-specific details so that
Cookie-based auth, OAuth 2.0, API-key auth, and any future scheme can all
be swapped in without changing the provider or service layers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AuthCredentials:
    """Generic carrier for HTTP authentication material.

    Providers apply these credentials to their HTTP sessions without
    knowing which authentication strategy produced them.

    Attributes:
        headers: HTTP headers to add to requests (e.g. ``Authorization``).
        cookies: HTTP cookies to attach to requests.
    """

    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)


class AuthProvider(ABC):
    """Abstract base class for authentication strategies.

    Implementations are responsible for obtaining and refreshing credentials
    through a specific mechanism (session cookies, OAuth 2.0 tokens, API
    keys, etc.).  They must never be imported by the core domain layer.

    Example usage::

        auth = ChessComCookieAuth()           # concrete implementation
        provider = ChessComClient(auth=auth)   # injected into provider
        service = ClubService(provider)        # provider injected into service
    """

    @abstractmethod
    def get_credentials(self) -> AuthCredentials:
        """Return the current credentials, refreshing them if necessary.

        Returns:
            An :class:`AuthCredentials` instance ready to be applied to an
            HTTP session.

        Raises:
            AuthenticationRequiredError: If no valid credentials are
                available and cannot be obtained automatically.
        """

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Return ``True`` if valid credentials are currently available.

        This method must not raise; it should silently return ``False``
        when credentials are absent or cannot be resolved.

        Returns:
            ``True`` if :meth:`get_credentials` would succeed.
        """
