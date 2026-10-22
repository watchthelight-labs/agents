import base64
import hashlib
import json
import re
import pytest
from urllib.parse import parse_qs, urlsplit

from starlette.testclient import TestClient

from memory_mcp.auth import ISSUER, RESOURCE, password_hash
from memory_mcp.memory import Memory
from memory_mcp.server import create_app
from memory_mcp.store import Store


@pytest.mark.parametrize("callback", ["https://claude.ai/api/mcp/auth_callback", "https://chatgpt.com/connector/oauth/test-connection", "https://chatgpt.com/connector_platform_oauth_redirect"])
def test_owner_oauth_boundaries_and_refresh(tmp_path, monkeypatch, callback):
    monkeypatch.setenv("MEMORY_USERNAME", "owner")
    monkeypatch.setenv("MEMORY_PASSWORD_HASH", password_hash("test password"))
    legacy = "legacy-" + "x" * 48
    with TestClient(create_app(tmp_path, legacy), base_url=ISSUER) as client:
        denied = client.post("/mcp")
        assert denied.status_code == 401
        assert "oauth-protected-resource/mcp" in denied.headers["www-authenticate"]
        assert client.get("/.well-known/oauth-protected-resource/mcp").json()["resource"] == RESOURCE
        metadata = client.get("/.well-known/oauth-authorization-server").json()
        assert metadata["registration_endpoint"] == ISSUER + "/register"
        registration = {"redirect_uris": [callback],
                        "token_endpoint_auth_method": "client_secret_post",
                        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]}
        assert client.post("/register", json={**registration, "redirect_uris": ["https://evil.example/callback"]}).status_code == 400
        assert client.post("/register", json={**registration, "redirect_uris": ["https://chatgpt.com/unrelated"]}).status_code == 400
        registered = client.post("/register", json=registration)
        assert registered.status_code == 201
        credentials = {key: registered.json()[key] for key in ("client_id", "client_secret")}
        verifier = "v" * 64
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params = {"client_id": credentials["client_id"], "redirect_uri": registration["redirect_uris"][0],
                  "response_type": "code", "code_challenge": challenge, "code_challenge_method": "S256",
                  "state": "opaque-client-state", "resource": RESOURCE, "scope": "memory"}
        assert client.get("/authorize", params={**params, "redirect_uri": "https://evil.example"}, follow_redirects=False).status_code == 400
        page = client.get("/authorize", params=params)
        assert page.status_code == 200
        assert page.headers["referrer-policy"] == "same-origin"
        fields = {name: re.search(f'name="{name}" value="([^"]+)"', page.text).group(1) for name in ("flow", "csrf")}
        fields.update(username="owner", password="test password")
        # Opening another connection window must not invalidate the first form.
        other_page = client.get("/authorize", params=params)
        assert other_page.status_code == 200
        # Refreshing the first window must also preserve its existing form token.
        assert client.get("/login", params={"flow": fields["flow"]}).status_code == 200
        assert client.post("/login", data=fields, headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.post("/login", data={**fields, "csrf": "bad"}, headers={"Origin": ISSUER}).status_code == 403
        assert client.post("/login", data={**fields, "password": "wrong"}, headers={"Origin": ISSUER}).status_code == 401
        login = client.post("/login", data=fields, headers={"Origin": ISSUER}, follow_redirects=False)
        assert login.status_code == 303
        callback = parse_qs(urlsplit(login.headers["location"]).query)
        assert callback["state"] == [params["state"]]
        exchange = {**credentials, "grant_type": "authorization_code", "code": callback["code"][0],
                    "redirect_uri": params["redirect_uri"], "code_verifier": verifier, "resource": RESOURCE}
        assert client.post("/token", data={**exchange, "code_verifier": "incorrect"}).status_code == 400
        tokens = client.post("/token", data=exchange)
        assert tokens.status_code == 200, tokens.text
        assert client.post("/token", data=exchange).status_code == 400
        tokens = tokens.json()
        initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "oauth-check", "version": "1"}}}
        def access(raw):
            return client.post("/mcp", json=initialize, headers={"Authorization": "Bearer " + raw, "Accept": "application/json, text/event-stream"})
        assert access(tokens["access_token"]).status_code == 200
        assert access(legacy).status_code == 200
        refresh_request = {**credentials, "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]}
        refreshed = client.post("/token", data=refresh_request)
        assert refreshed.status_code == 200
        assert client.post("/token", data=refresh_request).status_code == 400
        assert access(tokens["access_token"]).status_code == 401
        new_tokens = refreshed.json()
        assert access(new_tokens["access_token"]).status_code == 200
        boot = lambda raw: client.get("/boot?part=threads", headers={"Authorization": "Bearer " + raw} if raw else {})
        assert boot(None).status_code == 401 and boot("wrong").status_code == 401
        assert boot(new_tokens["access_token"]).status_code == 200 and boot(legacy).status_code == 200
        # OAuth apps (claude.ai, ChatGPT) never see private notes; Claude Code's own token does.
        mem = Memory(Store(tmp_path))
        mem.remember("Private thing", "zanzibar private detail", "fact", sensitivity="private", surface="test")
        def search(raw):
            headers = {"Authorization": "Bearer " + raw, "Accept": "application/json, text/event-stream"}
            version = access(raw).json()["result"]["protocolVersion"]
            call = {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                    "params": {"name": "search_memory", "arguments": {"query": "zanzibar"}}}
            reply = client.post("/mcp", json=call, headers={**headers, "MCP-Protocol-Version": version}).json()["result"]
            return json.loads(reply["content"][0]["text"])["results"]
        assert search(new_tokens["access_token"]) == [] and len(search(legacy)) == 1
        # A fresh app instance must recognize persisted tokens after a deployment/restart.
        with TestClient(create_app(tmp_path, legacy), base_url=ISSUER) as restarted:
            assert restarted.post("/mcp", json=initialize, headers={"Authorization": "Bearer " + new_tokens["access_token"], "Accept": "application/json, text/event-stream"}).status_code == 200
        assert client.post("/revoke", data={**credentials, "token": new_tokens["refresh_token"]}).status_code == 200
        assert access(new_tokens["access_token"]).status_code == 401
