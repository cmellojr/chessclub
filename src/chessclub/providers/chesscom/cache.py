"""SQLite-backed HTTP response cache for the Chess.com provider.

All cached entries live in a single SQLite database at
``~/.cache/chessclub/cache.db``.  Only HTTP 200 responses are stored;
errors are never cached.

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

import json
import sqlite3
import time
from pathlib import Path


class SQLiteCache:
    """SQLite-backed JSON cache with per-entry TTL.

    All entries are stored in a single SQLite database file::

        ~/.cache/chessclub/cache.db

    Schema::

        CREATE TABLE cache (
            key        TEXT PRIMARY KEY,
            expires_at REAL NOT NULL,
            body       TEXT NOT NULL
        )

    WAL journal mode is enabled for better concurrent read performance.
    Expired entries are removed lazily on the first read attempt.
    All write and read failures are silently ignored so that an
    inaccessible filesystem never breaks the application.

    Args:
        path: Path to the SQLite database file.  Defaults to
            ``~/.cache/chessclub/cache.db``.
    """

    _DB_PATH: Path = Path.home() / ".cache" / "chessclub" / "cache.db"

    def __init__(self, path: Path | None = None):
        self._path = path or self._DB_PATH
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
        except (sqlite3.Error, OSError):
            pass  # Non-fatal — cache becomes a no-op.

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key        TEXT PRIMARY KEY,
                    expires_at REAL NOT NULL,
                    body       TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expires "
                "ON cache (expires_at)"
            )

    def _delete(self, key: str) -> None:
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------
    # Public interface (same as the former DiskCache)
    # ------------------------------------------------------------------

    def get(self, key: str) -> dict | None:
        """Return the cached response body, or ``None`` on miss or expiry.

        Args:
            key: Canonical cache key (URL with serialised query params).

        Returns:
            The cached JSON body dict, or ``None``.
        """
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT body, expires_at FROM cache WHERE key = ?",
                    (key,),
                ).fetchone()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        body_json, expires_at = row
        if expires_at <= time.time():
            self._delete(key)
            return None
        try:
            return json.loads(body_json)
        except (ValueError, TypeError):
            return None

    def set(self, key: str, body: dict, ttl: int) -> None:
        """Write *body* to the cache with a time-to-live of *ttl* seconds.

        Args:
            key: Canonical cache key.
            body: JSON-serialisable response body to store.
            ttl: Seconds until the entry expires.
        """
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, expires_at, body) "
                    "VALUES (?, ?, ?)",
                    (key, time.time() + ttl, json.dumps(body)),
                )
        except (sqlite3.Error, OSError):
            pass  # Non-fatal.

    # ------------------------------------------------------------------
    # Cache management (used by the CLI cache commands)
    # ------------------------------------------------------------------

    def clear(self) -> int:
        """Delete all cache entries.

        Returns:
            Number of entries deleted.
        """
        try:
            with self._connect() as conn:
                return conn.execute("DELETE FROM cache").rowcount
        except sqlite3.Error:
            return 0

    def purge_expired(self) -> int:
        """Delete only entries whose TTL has elapsed.

        Returns:
            Number of entries deleted.
        """
        try:
            with self._connect() as conn:
                return conn.execute(
                    "DELETE FROM cache WHERE expires_at <= ?",
                    (time.time(),),
                ).rowcount
        except sqlite3.Error:
            return 0

    def stats(self) -> dict:
        """Return cache statistics.

        Returns:
            Dict with keys ``total``, ``active``, ``expired``,
            ``size_bytes``.  Empty dict on error.
        """
        try:
            now = time.time()
            with self._connect() as conn:
                total = conn.execute(
                    "SELECT COUNT(*) FROM cache"
                ).fetchone()[0]
                expired = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE expires_at <= ?",
                    (now,),
                ).fetchone()[0]
            size = self._path.stat().st_size if self._path.exists() else 0
            return {
                "total": total,
                "active": total - expired,
                "expired": expired,
                "size_bytes": size,
            }
        except (sqlite3.Error, OSError):
            return {}


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
