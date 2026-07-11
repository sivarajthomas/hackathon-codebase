"""Authentication package.

Provides pluggable authentication primitives used by MCP servers. The default
implementations are intentionally minimal placeholders; production deployments
should back these with Google Cloud IAM / identity tokens or an API-gateway.
"""

from shared.auth.authenticator import (
    Authenticator,
    NoOpAuthenticator,
    Principal,
    StaticTokenAuthenticator,
)

__all__ = [
    "Authenticator",
    "Principal",
    "NoOpAuthenticator",
    "StaticTokenAuthenticator",
]
