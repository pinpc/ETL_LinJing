"""Auth service placeholders."""

from __future__ import annotations

from .interfaces import AuthContext, IAuthProvider, IAuthorizationService


class AuthProvider(IAuthProvider):
    """Placeholder auth provider."""

    def authenticate(self, token: str) -> AuthContext:
        raise NotImplementedError("Phase 1 skeleton only.")


class AuthorizationService(IAuthorizationService):
    """Placeholder authorization service."""

    def can_access_tenant(self, context: AuthContext, tenant_id: str) -> bool:
        raise NotImplementedError("Phase 1 skeleton only.")

