"""Short-lived in-memory credential leases; credentials never enter job payloads."""

from __future__ import annotations

import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock


@dataclass
class _Lease:
    secret: str
    expires_at: float


class CredentialLeaseStore:
    def __init__(self, *, ttl_seconds: float = 300.0, clock=time.monotonic):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._leases: dict[str, _Lease] = {}
        self._lock = RLock()

    def put(self, secret: str) -> str:
        if not isinstance(secret, str) or not secret:
            raise ValueError("secret must be non-empty")
        with self._lock:
            self.purge_expired()
            lease_id = secrets.token_urlsafe(24)
            self._leases[lease_id] = _Lease(secret, self._clock() + self.ttl_seconds)
            return lease_id

    def get(self, lease_id: str) -> str | None:
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease is None:
                return None
            if lease.expires_at <= self._clock():
                self._leases.pop(lease_id, None)
                return None
            return lease.secret

    def consume(self, lease_id: str) -> str | None:
        with self._lock:
            lease = self._leases.pop(lease_id, None)
            if lease is None or lease.expires_at <= self._clock():
                return None
            return lease.secret

    def clear(self, lease_id: str) -> None:
        with self._lock:
            self._leases.pop(lease_id, None)

    def purge_expired(self) -> None:
        now = self._clock()
        for lease_id, lease in list(self._leases.items()):
            if lease.expires_at <= now:
                self._leases.pop(lease_id, None)

    def __len__(self) -> int:
        with self._lock:
            self.purge_expired()
            return len(self._leases)

    @contextmanager
    def lease(self, lease_id: str):
        """Yield a key for one operation and clear it even on provider failure."""

        # Consume under the store lock before yielding.  Looking up and then
        # clearing in ``finally`` would let two concurrent operations observe
        # the same one-time credential.
        secret = self.consume(lease_id)
        if secret is None:
            raise KeyError("credential lease is missing or expired")
        try:
            yield secret
        finally:
            self.clear(lease_id)


def secret_redacted(value: object) -> str:
    """Return a constant safe marker for logs and error objects."""

    return "[redacted]" if value else "[missing]"
