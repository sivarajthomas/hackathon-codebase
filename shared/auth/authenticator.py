"""Authentication primitives.

Defines the :class:`Authenticator` protocol and two placeholder implementations.
Servers depend on the *protocol*, not a concrete class, so authentication can be
swapped (e.g. for Google Cloud Run IAM / OIDC token verification) without
touching business code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from shared.exceptions import AuthenticationError
from shared.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Principal:
    """An authenticated caller identity."""

    subject: str
    claims: dict[str, Any] = field(default_factory=dict)


class Authenticator(ABC):
    """Abstract authentication strategy.

    Implementations validate a credential (token, header, etc.) and return a
    :class:`Principal`, or raise :class:`AuthenticationError`.
    """

    @abstractmethod
    def authenticate(self, credential: str | None) -> Principal:
        """Validate ``credential`` and return the authenticated principal."""
        raise NotImplementedError


class NoOpAuthenticator(Authenticator):
    """Authenticator that accepts everyone.

    Intended only for local development/testing. Never use in production.
    """

    def authenticate(self, credential: str | None) -> Principal:  # noqa: D102
        return Principal(subject="anonymous", claims={"auth": "noop"})


class StaticTokenAuthenticator(Authenticator):
    """Validate a caller against a set of pre-shared bearer tokens.

    The tokens are supplied at construction time from configuration (never
    hardcoded). This is a simple stopgap; production should verify signed OIDC
    identity tokens issued by Google.

    Args:
        valid_tokens: Mapping of token -> subject identity.
    """

    def __init__(self, valid_tokens: dict[str, str]) -> None:
        self._valid_tokens = dict(valid_tokens)

    def authenticate(self, credential: str | None) -> Principal:  # noqa: D102
        if not credential:
            raise AuthenticationError("Missing credential.")

        token = credential.removeprefix("Bearer ").strip()
        subject = self._valid_tokens.get(token)
        if subject is None:
            logger.warning("Authentication failed for supplied credential.")
            raise AuthenticationError("Invalid credential.")

        return Principal(subject=subject, claims={"auth": "static_token"})

    # TODO: Add GoogleOIDCAuthenticator that verifies Cloud Run identity tokens
    #       using google.oauth2.id_token.verify_oauth2_token against the
    #       expected audience. Keep it behind the Authenticator interface.
