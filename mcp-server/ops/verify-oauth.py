"""Exercise the deployed owner login without printing or retaining credentials."""
import base64
import getpass
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys
from urllib.parse import parse_qs, urlsplit

import httpx2

BASE = "https://mcp.example.org"
password = getpass.getpass("Owner password: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\r\n")
with httpx2.Client(timeout=30, follow_redirects=False) as client:
    response = client.post(BASE + "/mcp")
    assert response.status_code == 401
    assert "resource_metadata" in response.headers["www-authenticate"]
    metadata = client.get(BASE + "/.well-known/oauth-authorization-server").json()
    registered = client.post(metadata["registration_endpoint"], json={
        "client_name": "Bash Memory deployment check",
        "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        "token_endpoint_auth_method": "client_secret_post",
    })
    assert registered.status_code == 201
    credentials = {key: registered.json()[key] for key in ("client_id", "client_secret")}
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    params = {"client_id": credentials["client_id"], "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
              "response_type": "code", "code_challenge": challenge, "code_challenge_method": "S256",
              "state": secrets.token_urlsafe(24), "scope": "memory", "resource": BASE + "/mcp"}
    authorize = client.get(metadata["authorization_endpoint"], params=params)
    assert authorize.status_code == 302
    page = client.get(authorize.headers["location"])
    assert page.status_code == 200
    fields = {name: re.search(f'name="{name}" value="([^"]+)"', page.text).group(1) for name in ("flow", "csrf")}
    fields.update(username="watchthelight", password=password)
    login = client.post(BASE + "/login", data=fields, headers={"Origin": BASE})
    assert login.status_code == 303, "Owner login rejected"
    callback = parse_qs(urlsplit(login.headers["location"]).query)
    assert callback["state"] == [params["state"]]
    exchange = {**credentials, "grant_type": "authorization_code", "code": callback["code"][0],
                "redirect_uri": params["redirect_uri"], "code_verifier": verifier, "resource": BASE + "/mcp"}
    response = client.post(metadata["token_endpoint"], data=exchange)
    assert response.status_code == 200
    tokens = response.json()
    assert client.post(metadata["token_endpoint"], data=exchange).status_code == 400
    initialize = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "oauth-deployment-check", "version": "1"}}}
    legacy = json.loads((Path(__file__).resolve().parents[1] / "private/connection.json").read_text())["token"]
    for token in (tokens["access_token"], legacy):
        response = client.post(BASE + "/mcp", json=initialize, headers={"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"})
        assert response.status_code == 200
        assert response.json()["result"]["serverInfo"]["name"] == "Bash Memory"
    refreshed = client.post(metadata["token_endpoint"], data={**credentials, "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    revoked = client.post(metadata["revocation_endpoint"], data={**credentials, "token": refreshed.json()["refresh_token"]})
    assert revoked.status_code == 200
print("Public HTTPS: discovery, owner login, PKCE exchange, replay rejection, MCP access, legacy access, refresh and revocation passed.")
