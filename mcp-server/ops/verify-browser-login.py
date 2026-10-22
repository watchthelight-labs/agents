"""Check real browser form headers using an installed Edge and Playwright."""
import base64
import hashlib
import secrets
import sys
from urllib.parse import urlencode, urlsplit, parse_qs

from playwright.sync_api import sync_playwright

BASE = "https://mcp.example.org"
CALLBACK = "https://chatgpt.com/connector/oauth/deployment-check" if "--chatgpt" in sys.argv else "https://claude.ai/api/mcp/auth_callback"
password = sys.stdin.readline().rstrip("\r\n") if "--complete" in sys.argv else None
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    context = browser.new_context()
    registration = context.request.post(BASE + "/register", data={
        "client_name": "Browser form regression check",
        "redirect_uris": [CALLBACK],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"], "token_endpoint_auth_method": "client_secret_post",
    })
    assert registration.status == 201
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    params = {"client_id": registration.json()["client_id"], "redirect_uri": CALLBACK,
              "response_type": "code", "code_challenge": challenge, "code_challenge_method": "S256",
              "state": secrets.token_urlsafe(24), "scope": "memory", "resource": BASE + "/mcp"}
    page = context.new_page()
    page.on("console", lambda message: print("Browser blocked a form-action redirect") if "form-action" in message.text else None)
    page.goto(BASE + "/authorize?" + urlencode(params))
    other_page = context.new_page()
    other_page.goto(BASE + "/authorize?" + urlencode(params))
    page.reload()
    page.get_by_label("Username").fill("watchthelight")
    page.get_by_label("Password").fill("intentionally-incorrect-password")
    with page.expect_response(lambda response: response.url == BASE + "/login" and response.request.method == "POST") as pending:
        page.get_by_role("button", name="Sign in and connect").click()
    response = pending.value
    page.wait_for_url(BASE + "/login")
    page.wait_for_load_state("domcontentloaded")
    print("Browser form Origin:", response.request.all_headers().get("origin", "(absent)"))
    print("Login response status:", response.status)
    assert response.status == int(sys.argv[1])
    if "--complete" in sys.argv:
        assert password, "Verification needs a password on stdin"
        context.route(CALLBACK + "?*", lambda route: route.fulfill(status=200, body="Callback captured for verification."))
        page.get_by_label("Username").fill("watchthelight")
        page.get_by_label("Password").fill(password)
        with page.expect_response(lambda response: response.url == BASE + "/login" and response.request.method == "POST") as pending:
            page.get_by_role("button", name="Sign in and connect").click()
        response = pending.value
        assert response.status == 303
        callback = parse_qs(urlsplit(response.headers["location"]).query)
        assert callback["state"] == [params["state"]]
        credentials = {key: registration.json()[key] for key in ("client_id", "client_secret")}
        tokens = context.request.post(BASE + "/token", form={**credentials,
            "grant_type": "authorization_code", "code": callback["code"][0],
            "redirect_uri": params["redirect_uri"], "code_verifier": verifier, "resource": BASE + "/mcp"})
        assert tokens.status == 200
        revoked = context.request.post(BASE + "/revoke", form={**credentials, "token": tokens.json()["refresh_token"]})
        assert revoked.status == 200
        print("Real browser sign-in and OAuth code exchange passed; check tokens revoked.")
    browser.close()
