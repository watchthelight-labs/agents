"""Single-owner login; the MCP SDK owns OAuth validation and protocol endpoints."""

from collections import deque
from contextlib import contextmanager
import hashlib
import hmac
from html import escape
import json
import logging
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

import anyio
from mcp.server.auth.provider import (
    AccessToken, AuthorizationCode, AuthorizationParams, AuthorizeError,
    RefreshToken, RegistrationError, TokenError, construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.responses import HTMLResponse, RedirectResponse

ISSUER = "https://mcp.example.org"
RESOURCE = ISSUER + "/mcp"
SCOPE = "memory"
COOKIE = "__Host-memory-login"
PAGE_HEADERS = {
    # no-referrer makes browser form POSTs send Origin: null. same-origin keeps
    # the login origin while withholding referrers from the external callback.
    "Cache-Control": "no-store", "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self' https://claude.ai https://www.claude.ai https://claude.com https://chatgpt.com; frame-ancestors 'none'; base-uri 'none'",
    "X-Content-Type-Options": "nosniff",
}


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ":" + digest


class OwnerOAuth:
    def __init__(self, data_dir, legacy_token, username, hashed_password):
        if len(legacy_token) < 40:
            raise ValueError("MEMORY_TOKEN must contain at least 40 random characters")
        salt, digest = hashed_password.split(":")
        if len(bytes.fromhex(salt)) != 16 or len(bytes.fromhex(digest)) != 64:
            raise ValueError("Invalid owner password hash")
        self.path = data_dir / "oauth.sqlite3"
        self.legacy_token = legacy_token
        self.username = username
        self.hashed_password = hashed_password
        self.attempts = deque()
        with self.db() as con:
            con.execute("CREATE TABLE IF NOT EXISTS auth (kind TEXT, key TEXT, value TEXT NOT NULL, expires REAL NOT NULL, PRIMARY KEY(kind,key))")

    @contextmanager
    def db(self):
        con = sqlite3.connect(self.path, timeout=10)
        try:
            with con:
                yield con
        finally:
            con.close()

    def put(self, con, kind, key, value, expires):
        con.execute("DELETE FROM auth WHERE expires < ?", (time.time(),))
        con.execute("INSERT OR REPLACE INTO auth VALUES (?,?,?,?)", (kind, key, json.dumps(value), expires))

    def get(self, kind, key):
        with self.db() as con:
            row = con.execute("SELECT value FROM auth WHERE kind=? AND key=? AND expires>?", (kind, key, time.time())).fetchone()
        return json.loads(row[0]) if row else None

    @staticmethod
    def key(token):
        return hashlib.sha256(token.encode()).hexdigest()

    async def get_client(self, client_id):
        value = self.get("client", client_id)
        return OAuthClientInformationFull.model_validate(value) if value else None

    async def register_client(self, client_info):
        # Restrict DCR to the supported clients; the SDK binds each grant to the
        # exact URI registered here. ChatGPT uses per-connector callback IDs.
        for uri in client_info.redirect_uris:
            parsed = urlsplit(str(uri))
            chatgpt_callback = parsed.hostname == "chatgpt.com" and (
                parsed.path == "/connector_platform_oauth_redirect" or
                (parsed.path.startswith("/connector/oauth/") and bool(parsed.path.removeprefix("/connector/oauth/"))
                 and "/" not in parsed.path.removeprefix("/connector/oauth/"))) and not parsed.query
            known_client = parsed.hostname in {"claude.ai", "www.claude.ai", "claude.com"} or chatgpt_callback
            if parsed.scheme != "https" or not known_client or parsed.port not in {None, 443} or parsed.username or parsed.password or parsed.fragment:
                raise RegistrationError("invalid_redirect_uri", "Use a supported Claude or ChatGPT HTTPS callback URL")
        with self.db() as con:
            con.execute("DELETE FROM auth WHERE expires < ?", (time.time(),))
            if con.execute("SELECT count(*) FROM auth WHERE kind='client'").fetchone()[0] >= 1000:
                raise RegistrationError("invalid_client_metadata", "Registration capacity reached")
            self.put(con, "client", client_info.client_id, client_info.model_dump(mode="json"), time.time() + 365 * 86400)

    async def authorize(self, client, params):
        if params.resource not in {None, RESOURCE}:
            raise AuthorizeError("invalid_target", "Unknown resource")
        if params.scopes and set(params.scopes) != {SCOPE}:
            raise AuthorizeError("invalid_scope", "Unknown scope")
        flow = secrets.token_urlsafe(32)
        with self.db() as con:
            self.put(con, "flow", self.key(flow), {"client_id": client.client_id, "params": params.model_dump(mode="json")}, time.time() + 600)
        return ISSUER + "/login?flow=" + flow

    async def login(self, request):
        if request.method == "GET":
            flow = request.query_params.get("flow", "")
            if not self.get("flow", self.key(flow)):
                return HTMLResponse("This sign-in link expired. Connect again from Claude.", status_code=400, headers=PAGE_HEADERS)
            cookie_name = COOKIE + "-" + self.key(flow)
            csrf = request.cookies.get(cookie_name, "")
            binding = self.get("csrf", self.key(csrf)) if csrf else None
            if not binding or binding["flow"] != self.key(flow):
                csrf = secrets.token_urlsafe(32)
            with self.db() as con:
                self.put(con, "csrf", self.key(csrf), {"flow": self.key(flow)}, time.time() + 600)
            response = self.page(flow, csrf)
            response.set_cookie(cookie_name, csrf, secure=True, httponly=True, samesite="lax", max_age=600, path="/")
            return response

        if request.headers.get("origin") != ISSUER:
            return HTMLResponse("Invalid sign-in origin.", status_code=403, headers=PAGE_HEADERS)
        form = await request.form()
        flow, csrf = str(form.get("flow", "")), str(form.get("csrf", ""))
        cookie_name = COOKIE + "-" + self.key(flow)
        cookie = request.cookies.get(cookie_name, "")
        binding = self.get("csrf", self.key(csrf))
        pending = self.get("flow", self.key(flow))
        if not pending:
            logging.getLogger(__name__).warning("Login rejected: flow expired or already used")
            return HTMLResponse("This sign-in link expired. Connect again from Claude.", status_code=403, headers=PAGE_HEADERS)
        if not cookie:
            logging.getLogger(__name__).warning("Login rejected: browser cookie missing")
            return HTMLResponse("The browser did not send its sign-in cookie. Allow cookies for mcp.example.org, then connect again from Claude.", status_code=403, headers=PAGE_HEADERS)
        if not csrf or not hmac.compare_digest(csrf.encode(), cookie.encode()) or not binding or binding["flow"] != self.key(flow):
            logging.getLogger(__name__).warning("Login rejected: form and browser binding mismatch")
            return HTMLResponse("This form no longer matches the browser session. Reload the sign-in page from Claude and try again.", status_code=403, headers=PAGE_HEADERS)
        now = time.time()
        while self.attempts and self.attempts[0] < now - 60:
            self.attempts.popleft()
        if len(self.attempts) >= 10:
            return self.page(flow, csrf, "Too many attempts. Wait one minute and try again.", 429)
        self.attempts.append(now)
        password = str(form.get("password", ""))
        supplied = await anyio.to_thread.run_sync(password_hash, password, self.hashed_password.split(":")[0])
        valid_password = hmac.compare_digest(supplied, self.hashed_password)
        if not hmac.compare_digest(str(form.get("username", "")).encode(), self.username.encode()) or not valid_password:
            return self.page(flow, csrf, "Username or password is incorrect.", 401)
        params = AuthorizationParams.model_validate(pending["params"])
        code = secrets.token_urlsafe(32)
        grant = AuthorizationCode(code=code, client_id=pending["client_id"], scopes=[SCOPE], expires_at=now + 120,
                                  code_challenge=params.code_challenge, redirect_uri=params.redirect_uri,
                                  redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
                                  resource=RESOURCE, subject=self.username)
        with self.db() as con:
            removed = con.execute("DELETE FROM auth WHERE kind='flow' AND key=? AND expires>?", (self.key(flow), time.time())).rowcount
            if not removed:
                return HTMLResponse("Sign-in already completed. Connect again from Claude.", status_code=400, headers=PAGE_HEADERS)
            con.execute("DELETE FROM auth WHERE kind='csrf' AND key=?", (self.key(csrf),))
            self.put(con, "code", self.key(code), grant.model_dump(mode="json", exclude={"code"}), grant.expires_at)
        response = RedirectResponse(construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state), status_code=303, headers=PAGE_HEADERS)
        response.delete_cookie(cookie_name, secure=True, httponly=True, samesite="lax")
        return response

    def page(self, flow, csrf, error="", status=200):
        return HTMLResponse(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign in to Bash Memory</title><style>body{{font:18px system-ui;background:#151918;color:#edf2ec;max-width:430px;margin:10vh auto;padding:24px}}label,input,button{{display:block;width:100%;box-sizing:border-box}}input,button{{font:inherit;padding:12px;margin:8px 0 24px;border-radius:6px}}button{{background:#b5c9aa;cursor:pointer}}.error{{color:#ffb8af}}</style>
<h1>Bash Memory</h1><p>Sign in to let your assistant search your private library and save or revise notes when you ask.</p><p class="error" role="alert">{escape(error)}</p>
<form method="post" action="/login"><input type="hidden" name="flow" value="{escape(flow, quote=True)}"><input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">
<label for="username">Username</label><input id="username" name="username" autocomplete="username" required maxlength="100">
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="256">
<button type="submit">Sign in and connect</button></form></html>''', status_code=status, headers=PAGE_HEADERS)

    async def load_authorization_code(self, client, authorization_code):
        value = self.get("code", self.key(authorization_code))
        return AuthorizationCode(code=authorization_code, **value) if value and value["client_id"] == client.client_id else None

    def issue(self, con, client_id, scopes):
        now = int(time.time())
        access, refresh = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        group = secrets.token_hex(16)
        for kind, raw, expiry in [("access", access, now + 3600), ("refresh", refresh, now + 30 * 86400)]:
            self.put(con, kind, self.key(raw), {"client_id": client_id, "scopes": scopes, "expires_at": expiry, "resource": RESOURCE, "subject": self.username, "group": group}, expiry)
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=3600, refresh_token=refresh, scope=" ".join(scopes))

    async def exchange_authorization_code(self, client, authorization_code):
        with self.db() as con:
            removed = con.execute("DELETE FROM auth WHERE kind='code' AND key=? AND expires>?", (self.key(authorization_code.code), time.time())).rowcount
            if not removed:
                raise TokenError("invalid_grant", "Code expired or already used")
            return self.issue(con, client.client_id, authorization_code.scopes)

    async def load_refresh_token(self, client, refresh_token):
        value = self.get("refresh", self.key(refresh_token))
        return RefreshToken(token=refresh_token, **value) if value and value["client_id"] == client.client_id else None

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        with self.db() as con:
            row = con.execute("DELETE FROM auth WHERE kind='refresh' AND key=? AND expires>? RETURNING value", (self.key(refresh_token.token), time.time())).fetchone()
            if not row:
                raise TokenError("invalid_grant", "Refresh token expired or already used")
            group = json.loads(row[0])["group"]
            con.execute("DELETE FROM auth WHERE kind='access' AND json_extract(value,'$.group')=?", (group,))
            return self.issue(con, client.client_id, scopes)

    async def load_access_token(self, token):
        if hmac.compare_digest(token.encode(), self.legacy_token.encode()):
            return AccessToken(token=token, client_id="claude-code", scopes=[SCOPE], resource=RESOURCE, subject=self.username)
        value = self.get("access", self.key(token))
        return AccessToken(token=token, **value) if value else None

    async def revoke_token(self, token):
        value = self.get("access", self.key(token.token)) or self.get("refresh", self.key(token.token))
        if value:
            with self.db() as con:
                con.execute("DELETE FROM auth WHERE kind IN ('access','refresh') AND json_extract(value,'$.group')=?", (value["group"],))
