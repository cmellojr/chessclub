"""Disk-backed HTTP response cache for the Chess.com provider.

Cached entries live under ``~/.cache/chessclub/`` as JSON files named
after the SHA-256 of the request URL (query parameters included in the
key).  Only HTTP 200 responses are stored; errors are never cached.

TTL policy (set by :meth:`ChessComClient._cache_ttl`):

+-------------------------------------------+-------------+--------------------------------------------+
| URL pattern                               | TTL         | Rationale                                  |
+===========================================+=============+============================================+
| ``/games/{year}/{month}`` (past month)    | 30 days     | Historical archives are immutable          |
+-------------------------------------------+-------------+--------------------------------------------+
| ``/games/{year}/{month}`` (current month) | 1 hour      | Tournament rounds span hours, not minutes  |
+-------------------------------------------+-------------+--------------------------------------------+
| ``/pub/player/{username}``                | 24 hours    | Rating/title updated at most once per day  |
+-------------------------------------------+-------------+--------------------------------------------+
| ``/pub/club/{slug}/members``              | 1 hour      | Joins/leaves are infrequent events         |
+-------------------------------------------+-------------+--------------------------------------------+
| ``/pub/club/{slug}``                      | 24 hours    | Club name/description almost never changes |
+-------------------------------------------+-------------+--------------------------------------------+
| ``*/leaderboard``                         | 7 days      | Finished tournaments are immutable         |
+-------------------------------------------+-------------+--------------------------------------------+
| ``/clubs/live/past/{id}``                 | 30 minutes  | New tournaments appear weekly at most      |
+-------------------------------------------+-------------+--------------------------------------------+
"""

import hashlib
import json
import time
from pathlib import Path

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "chessclub"


class DiskCache:
    """File-backed JSON cache with per-entry TTL.

    Each entry is a JSON file ``{sha256_of_key}.json`` containing::

        {"expires_at": <unix_timestamp>, "body": <response_dict>}

    Expired entries are removed lazily on the first read attempt.
    Write failures are silently ignored so that a read-only filesystem
    never breaks the application.

    Args:
        cache_dir: Directory for cache files.  Defaults to
            ``~/.cache/chessclub/``.
    """

    def __init__(self, cache_dir: Path = _DEFAULT_CACHE_DIR):
        self._dir = cache_dir
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # Non-fatal — cache will silently become a no-op.

    def get(self, key: str) -> dict | None:
        """Return the cached response body, or ``None`` on miss or expiry.

        Args:
            key: Canonical cache key (URL with serialised query params).

        Returns:
            The cached JSON body dict, or ``None``.
        """
        path = self._path(key)
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if time.time() > entry.get("expires_at", 0):
            try:
                path.unlink()
            except OSError:
                pass
            return None
        return entry.get("body")

    def set(self, key: str, body: dict, ttl: int) -> None:
        """Write *body* to the cache with a time-to-live of *ttl* seconds.

        Args:
            key: Canonical cache key.
            body: JSON-serialisable response body to store.
            ttl: Seconds until the entry expires.
        """
        path = self._path(key)
        try:
            path.write_text(
                json.dumps({"expires_at": time.time() + ttl, "body": body}),
                encoding="utf-8",
            )
        except OSError:
            pass  # Non-fatal.

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode()).hexdigest()
        return self._dir / f"{h}.json"


class CachedResponse:
    """Lightweight stub that mimics the :class:`requests.Response` interface.

    Implements only the subset used by :class:`~chessclub.providers.chesscom
    .client.ChessComClient`: ``status_code``, ``json()``, and
    ``raise_for_status()``.  Always reports HTTP 200 because only successful
    responses are written to the cache.

    Args:
        body: The cached JSON response body.
    """

    status_code: int = 200

    def __init__(self, body: dict):
        self._body = body

    def json(self) -> dict:
        """Return the cached response body.

        Returns:
            The response body dict.
        """
        return self._body

    def raise_for_status(self) -> None:
        """No-op — cached responses always represent HTTP 200."""
