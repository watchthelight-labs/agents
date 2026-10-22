import time

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest
from starlette.testclient import TestClient

from memory_mcp.dash import create_dash
from memory_mcp.dash.access import AccessVerifier
from memory_mcp.memory import Memory
from memory_mcp.store import Store

TEAM, AUD, OWNER, ORIGIN = "watchthelight.cloudflareaccess.com", "aud-dashboard", "owner@example.org", "https://dash.example.org"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJWK:
    def __init__(self, key):
        self.key = key


def token(email=OWNER, aud=AUD, iss="https://" + TEAM, exp=3600, key=KEY):
    now = int(time.time())
    return jwt.encode({"email": email, "aud": [aud], "iss": iss, "iat": now, "exp": now + exp, "sub": "x"}, key,
                      algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture
def client(tmp_path, monkeypatch):
    verifier = AccessVerifier(TEAM, AUD, OWNER)
    monkeypatch.setattr(verifier.keys, "get_signing_key_from_jwt", lambda t: FakeJWK(KEY.public_key()))
    mem = Memory(Store(tmp_path))
    saved = mem.remember("Kelp timer is inverted", "The kelp timer output is inverted.", "gotcha", "project:srv10", surface="test")
    app = create_dash(tmp_path, verifier=verifier, origins=[ORIGIN], secret=b"s" * 32)
    with TestClient(app, base_url=ORIGIN) as c:
        c.saved = saved
        yield c


def h(tok=None, write=False, csrf=None, origin=ORIGIN):
    headers = {"Cf-Access-Jwt-Assertion": tok if tok is not None else token()}
    if write:
        headers.update({"Origin": origin, "X-CSRF": csrf or ""})
    return headers


def test_access_jwt_is_required_and_checked(client):
    assert client.get("/api/me").status_code == 403
    assert client.get("/api/me", headers=h("garbage")).status_code == 403
    assert client.get("/api/me", headers=h(token(aud="another-app"))).status_code == 403
    assert client.get("/api/me", headers=h(token(iss="https://evil.cloudflareaccess.com"))).status_code == 403
    assert client.get("/api/me", headers=h(token(email="someone@else.org"))).status_code == 403
    assert client.get("/api/me", headers=h(token(exp=-120))).status_code == 403
    forged = jwt.encode({"email": OWNER, "aud": AUD, "iss": "https://" + TEAM, "iat": 0, "exp": 9999999999}, OTHER_KEY,
                        algorithm="RS256", headers={"kid": "k1"})
    assert client.get("/api/me", headers=h(forged)).status_code == 403
    none_alg = jwt.encode({"email": OWNER, "aud": AUD, "iss": "https://" + TEAM, "iat": 0, "exp": 9999999999}, None, algorithm="none")
    assert client.get("/api/me", headers=h(none_alg)).status_code == 403
    me = client.get("/api/me", headers=h())
    assert me.status_code == 200 and me.json()["email"] == OWNER and me.headers["cache-control"] == "no-store"


def test_writes_need_origin_and_csrf(client):
    csrf = client.get("/api/me", headers=h()).json()["csrf"]
    note_id = client.saved["note_id"]
    url = f"/api/notes/{note_id}/verify"
    assert client.post(url, headers=h(write=True)).status_code == 403
    assert client.post(url, headers=h(write=True, csrf=csrf, origin="https://evil.example")).status_code == 403
    assert client.post(url, headers={"Cf-Access-Jwt-Assertion": token(), "X-CSRF": csrf}).status_code == 403
    ok = client.post(url, headers=h(write=True, csrf=csrf))
    assert ok.status_code == 200 and ok.json()["receipt"].startswith("📝 verified")


def test_note_lifecycle_and_revert_via_api(client):
    csrf = client.get("/api/me", headers=h()).json()["csrf"]
    w = h(write=True, csrf=csrf)
    overview = client.get("/api/overview", headers=h()).json()
    assert overview["status"]["notes"]["active"] == 1 and overview["projects"][0]["key"] == "srv10"
    note = client.get(f"/api/notes/{client.saved['note_id'][:8]}", headers=h()).json()
    edited = client.put(f"/api/notes/{note['note_id']}", headers=w,
                        json={"content": "Fixed by flipping the comparator.", "expected_version": note["current_version"]})
    assert edited.status_code == 200, edited.text
    stale = client.put(f"/api/notes/{note['note_id']}", headers=w, json={"content": "x", "expected_version": note["current_version"]})
    assert stale.status_code == 409
    old = client.get(f"/api/notes/{note['note_id']}/versions/{note['current_version']}", headers=h()).json()
    assert "inverted" in old["content"]
    reverted = client.post(f"/api/changes/{edited.json()['change_id']}/revert", headers=w, json={})
    assert reverted.status_code == 200
    assert "inverted" in client.get(f"/api/notes/{note['note_id']}", headers=h()).json()["content"]
    dup = client.post("/api/notes", headers=w, json={"title": "Kelp timer inverted", "content": "again", "type": "gotcha", "scope": "project:srv10"})
    assert dup.json()["status"] == "possible_duplicate"
    created = client.post("/api/notes", headers=w, json={"title": "Smokehouse output", "content": "North chest", "type": "fact", "scope": "project:srv10"})
    assert created.json()["status"] == "saved"
    assert client.post(f"/api/notes/{created.json()['note_id']}/archive", headers=w, json={"reason": "done"}).status_code == 200
    assert client.get("/api/notes?status=archived", headers=h()).json()["total"] == 1
    assert client.patch(f"/api/notes/{note['note_id']}/labels", headers=w, json={"pinned": True}).status_code == 200
    assert client.get("/api/notes/zzzz", headers=h()).status_code == 400
    assert client.get("/api/notes/" + "a" * 32, headers=h()).status_code == 404
    project = client.put("/api/projects/srv10", headers=w, json={"summary": "Main ATM10 server"}).json()
    assert project["summary"] == "Main ATM10 server"
    boot = client.get("/api/boot?project=srv10", headers=h()).json()
    assert boot["project"]["key"] == "srv10" and set(boot["parts"]) == {"profile", "project", "threads"}
    found = client.get("/api/search?q=kelp", headers=h()).json()["results"]
    assert found and client.get(f"/api/source/{found[0]['document_id']}", headers=h()).json()["passages"]
    assert client.get("/api/nope", headers=h()).status_code == 404
