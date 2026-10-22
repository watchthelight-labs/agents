"""Cloudflare Access is the dashboard's identity layer; every API request must carry its signed JWT.

Cloudflare adds `Cf-Access-Jwt-Assertion` after the owner signs in. The token is checked here too, so a request
that reaches the origin some other way, or carries an Access token minted for another application, is refused.
"""

import hashlib
import hmac
import secrets

import jwt


class AccessError(Exception):
    pass


class AccessVerifier:
    def __init__(self, team_domain, audience, owner_email):
        if not (team_domain and audience and owner_email):
            raise ValueError("CF_TEAM_DOMAIN, CF_ACCESS_AUD and OWNER_EMAIL are required")
        self.issuer = "https://" + team_domain.removeprefix("https://").rstrip("/")
        self.audience = audience
        self.owner = owner_email.lower()
        self.keys = jwt.PyJWKClient(self.issuer + "/cdn-cgi/access/certs", cache_keys=True, lifespan=3600, timeout=10)

    def verify(self, token):
        if not token:
            raise AccessError("Missing Cloudflare Access token")
        try:
            key = self.keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, key.key, algorithms=["RS256"], audience=self.audience, issuer=self.issuer,
                                options={"require": ["exp", "iat", "aud", "iss"]}, leeway=30)
        except jwt.PyJWTError as exc:
            raise AccessError(f"Invalid Cloudflare Access token ({type(exc).__name__})") from exc
        email = str(claims.get("email", "")).lower()
        if not hmac.compare_digest(email.encode(), self.owner.encode()):
            raise AccessError("This dashboard belongs to someone else")
        return email


class DevVerifier:
    """Local development only: no Cloudflare in front, the backend is bound to 127.0.0.1."""

    def __init__(self, email="dev@localhost"):
        self.email = email

    def verify(self, token):
        return self.email


def csrf_token(secret, email):
    return hmac.new(secret, ("csrf:" + email).encode(), hashlib.sha256).hexdigest()


def new_secret():
    return secrets.token_bytes(32)
