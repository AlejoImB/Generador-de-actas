"""Integración con Zitadel (SSO corporativo).

Solo se activa cuando ZITADEL_DOMAIN está configurado.
Implementa Authorization Code + PKCE para máxima seguridad.
"""
import json
import secrets
import hashlib
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings

settings = get_settings()

# Estado PKCE en memoria (state -> datos), TTL 10 minutos
_pending: dict[str, dict] = {}

# Cache JWKS para no refetchar en cada request
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.ZITADEL_DOMAIN.rstrip('/')}/oauth/v2/keys"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def create_pkce_pair() -> tuple[str, str]:
    """Retorna (code_verifier, code_challenge_S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_auth_url(state: str, code_challenge: str, callback_uri: str) -> str:
    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": settings.ZITADEL_CLIENT_ID,
        "redirect_uri": callback_uri,
        "scope": "openid profile email",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    })
    return f"{settings.ZITADEL_DOMAIN.rstrip('/')}/oauth/v2/authorize?{params}"


def save_state(state: str, code_verifier: str, frontend_redirect: str):
    _pending[state] = {
        "code_verifier": code_verifier,
        "frontend_redirect": frontend_redirect,
        "expires": datetime.now(timezone.utc) + timedelta(minutes=10),
    }


def pop_state(state: str) -> dict | None:
    data = _pending.pop(state, None)
    if not data:
        return None
    if datetime.now(timezone.utc) > data["expires"]:
        return None
    return data


def exchange_code(code: str, code_verifier: str, callback_uri: str) -> dict:
    """Intercambia el authorization code por tokens."""
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_uri,
        "client_id": settings.ZITADEL_CLIENT_ID,
        "client_secret": settings.ZITADEL_CLIENT_SECRET,
        "code_verifier": code_verifier,
    }).encode()
    req = urllib.request.Request(
        f"{settings.ZITADEL_DOMAIN.rstrip('/')}/oauth/v2/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def validate_id_token(id_token: str) -> dict:
    """Valida el ID token RS256 de Zitadel con JWKS."""
    client = _get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.ZITADEL_CLIENT_ID,
    )
    return claims
