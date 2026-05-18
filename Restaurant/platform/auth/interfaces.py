"""Auth module interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class AuthContext:
    """Represents authenticated actor context."""

    user_id: str
    roles: list[str]
    tenant_ids: list[str]


class IAuthProvider(Protocol):
    """Authentication provider contract."""

    def authenticate(self, token: str) -> AuthContext:
        """Authenticate token and return auth context."""


class IAuthorizationService(Protocol):
    """Authorization contract."""

    def can_access_tenant(self, context: AuthContext, tenant_id: str) -> bool:
        """Check tenant access."""

