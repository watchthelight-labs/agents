"""Create only the memory subdomain using existing local Cloudflare credentials."""
import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument("credentials", type=Path)
args = parser.parse_args()
lines = args.credentials.read_text(encoding="utf-8").splitlines()
def value(label):
    line = next(line for line in lines if label in line.lower())
    return line.strip("| ").split("|")[-1].strip().strip("`").strip()
email, key = value("account email"), value("global api key")
assert "@" in email and len(key) > 20
def request(path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request("https://api.cloudflare.com/client/v4" + path, data=body,
                  headers={"X-Auth-Email": email, "X-Auth-Key": key, "Content-Type": "application/json"})
    with urlopen(req, timeout=30) as response:
        result = json.load(response)
    if not result["success"]:
        raise RuntimeError("Cloudflare rejected DNS operation")
    return result["result"]
zone = request("/zones?name=example.org")[0]["id"]
existing = request(f"/zones/{zone}/dns_records?name=mcp.example.org")
if existing:
    if len(existing) != 1 or existing[0]["type"] != "A" or existing[0]["content"] != "203.0.113.10" or existing[0]["proxied"]:
        raise RuntimeError("An unexpected DNS record already exists; refusing to replace it")
    print("Expected DNS record already exists.")
else:
    result = request(f"/zones/{zone}/dns_records", {"type": "A", "name": "mcp.example.org", "content": "203.0.113.10", "ttl": 300, "proxied": False, "comment": "Private memory MCP; direct TLS on EC2"})
    print("Created DNS-only A record for mcp.example.org.")
