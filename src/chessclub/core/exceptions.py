"""Domain exceptions for the chessclub library."""


class ChessclubError(Exception):
    """Base class for all chessclub library exceptions."""


class AuthenticationRequiredError(ChessclubError):
    """Raised when an authenticated endpoint is called without credentials.

    The provider raises this exception when a request returns HTTP 401.
    The caller (CLI or application) is responsible for guiding the user
    through the authentication flow — the provider itself has no knowledge
    of how credentials are obtained or stored.
    """


class ProviderError(ChessclubError):
    """Raised when a provider encounters an unrecoverable error."""
