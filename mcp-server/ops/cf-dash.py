"""Provision Cloudflare for dash.example.org. Idempotent: each step checks before creating.

    python ops/cf-dash.py            # plan only: shows what exists and what would change
    python ops/cf-dash.py --apply

Steps: Origin CA certificate (origin TLS), a private CA + client certificate for per-hostname Authenticated
Origin Pulls (so only Cloudflare reaches the origin), a proxied A record, an SSL Full (strict) configuration rule
for this hostname only, and a Cloudflare Access application allowing only the owner's email. Writes
private/dash/{origin.pem,origin.key,aop-ca.pem} and private/memory-dash.env. Reads credentials from
private/cloudflare.json ({email, account_id, key}); never prints secrets.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import secrets
import urllib.error
import urllib.request

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

HOST, ZONE, ORIGIN_IP = "dash.example.org", "example.org", "203.0.113.10"
OWNER = "owner@example.org"
APP_NAME = "watchthelight dashboard"
root = Path(__file__).resolve().parents[1]
out = root / "private" / "dash"
creds = json.loads((root / "private" / "cloudflare.json").read_text(encoding="utf-8"))
parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()


def cf(method, path, body=None):
    req = urllib.request.Request("https://api.cloudflare.com/client/v4" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Auth-Email": creds["email"], "X-Auth-Key": creds["key"],
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        data = json.load(exc)
    if not data.get("success"):
        raise RuntimeError(f"{method} {path}: {data.get('errors')}")
    return data["result"]


def pem_key(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def write_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())


def step(name, done):
    print(f"[{'ok' if done else 'todo' if not args.apply else 'make'}] {name}")
    return not done and args.apply


zone = cf("GET", f"/zones?name={ZONE}")[0]
zid, account = zone["id"], zone["account"]["id"]

# 1. Origin CA certificate for nginx (Cloudflare trusts it under Full (strict); 15 years, no renewals).
if step("Origin CA certificate", (out / "origin.pem").exists()):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOST)])) \
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(HOST)]), critical=False).sign(key, hashes.SHA256())
    cert = cf("POST", "/certificates", {"hostnames": [HOST], "requested_validity": 5475, "request_type": "origin-rsa",
                                        "csr": csr.public_bytes(serialization.Encoding.PEM).decode()})
    write_private(out / "origin.key", pem_key(key))
    write_private(out / "origin.pem", cert["certificate"])

# 2. Per-hostname Authenticated Origin Pulls with our own CA, so the origin rejects anything but this zone's proxy.
aop = cf("GET", f"/zones/{zid}/origin_tls_client_auth/hostnames/{HOST}") if (out / "aop-ca.pem").exists() else None
if step("Authenticated Origin Pulls (per hostname)", bool(aop and aop.get("enabled"))):
    ca_key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "watchthelight origin-pull CA")])
    ca = x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key()) \
        .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1)) \
        .not_valid_after(now + timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True) \
        .sign(ca_key, hashes.SHA256())
    client_key = ec.generate_private_key(ec.SECP256R1())
    client = x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "cloudflare-origin-pull " + HOST)])) \
        .issuer_name(ca_name).public_key(client_key.public_key()).serial_number(x509.random_serial_number()) \
        .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=3650)) \
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False).sign(ca_key, hashes.SHA256())
    uploaded = cf("POST", f"/zones/{zid}/origin_tls_client_auth/hostnames/certificates",
                  {"certificate": client.public_bytes(serialization.Encoding.PEM).decode(),
                   "private_key": pem_key(client_key).decode()})
    cf("PUT", f"/zones/{zid}/origin_tls_client_auth/hostnames",
       {"config": [{"hostname": HOST, "cert_id": uploaded["id"], "enabled": True}]})
    write_private(out / "aop-ca.pem", ca.public_bytes(serialization.Encoding.PEM))  # CA key is discarded on purpose.

# 3. Proxied DNS record.
records = cf("GET", f"/zones/{zid}/dns_records?name={HOST}")
if records and (records[0]["type"] != "A" or records[0]["content"] != ORIGIN_IP or not records[0]["proxied"]):
    raise RuntimeError("An unexpected DNS record for this hostname exists; refusing to change it")
if step("Proxied A record", bool(records)):
    cf("POST", f"/zones/{zid}/dns_records", {"type": "A", "name": HOST, "content": ORIGIN_IP, "ttl": 1, "proxied": True,
                                             "comment": "watchthelight dashboard; Access + origin pulls"})

# 4. SSL Full (strict) for this hostname only; the zone default (flexible) stays as is for the other sites.
expression = f'(http.host eq "{HOST}")'
try:
    phase = cf("GET", f"/zones/{zid}/rulesets/phases/http_config_settings/entrypoint")
except RuntimeError:
    phase = {"rules": []}
rules = [r for r in phase.get("rules", []) if r.get("expression") != expression]
have = any(r.get("expression") == expression and (r.get("action_parameters") or {}).get("ssl") == "strict"
           for r in phase.get("rules", []))
if step("SSL Full (strict) configuration rule", have):
    keep = [{k: r[k] for k in ("expression", "action", "action_parameters", "description", "enabled") if k in r} for r in rules]
    keep.append({"expression": expression, "action": "set_config", "action_parameters": {"ssl": "strict"},
                 "description": "dashboard origin uses an Origin CA certificate", "enabled": True})
    cf("PUT", f"/zones/{zid}/rulesets/phases/http_config_settings/entrypoint", {"rules": keep})

# 5. Access application limited to the owner (one-time PIN login).
org = cf("GET", f"/accounts/{account}/access/organizations")
apps = [a for a in cf("GET", f"/accounts/{account}/access/apps") if a.get("domain") == HOST]
if step("Access application", bool(apps)):
    idps = cf("GET", f"/accounts/{account}/access/identity_providers")
    otp = next((i for i in idps if i["type"] == "onetimepin"), None) or \
        cf("POST", f"/accounts/{account}/access/identity_providers", {"name": "One-time PIN", "type": "onetimepin", "config": {}})
    policy = cf("POST", f"/accounts/{account}/access/policies",
                {"name": "dashboard owner only", "decision": "allow", "include": [{"email": {"email": OWNER}}],
                 "session_duration": "24h"})
    apps = [cf("POST", f"/accounts/{account}/access/apps",
               {"name": APP_NAME, "domain": HOST, "type": "self_hosted", "session_duration": "24h",
                "allowed_idps": [otp["id"]], "auto_redirect_to_identity": True, "app_launcher_visible": False,
                "http_only_cookie_attribute": True, "same_site_cookie_attribute": "lax",
                "policies": [{"id": policy["id"], "precedence": 1}]})]

if apps:
    env = root / "private" / "memory-dash.env"
    existing = dict(line.split("=", 1) for line in env.read_text().splitlines() if "=" in line) if env.exists() else {}
    values = {"MEMORY_DATA": "/srv/memory-mcp/data", "CF_TEAM_DOMAIN": org["auth_domain"], "CF_ACCESS_AUD": apps[0]["aud"],
              "OWNER_EMAIL": OWNER, "DASH_ORIGINS": "https://" + HOST,
              "DASH_SECRET": existing.get("DASH_SECRET") or secrets.token_hex(32)}
    env.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8", newline="\n")
    print("wrote private/memory-dash.env (team domain and AUD tag, no API secrets)")
