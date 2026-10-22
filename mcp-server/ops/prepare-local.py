"""Generate local connection material without printing credentials."""
import json
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
private = root / "private"
private.mkdir(exist_ok=True)
connection = private / "connection.json"
if not connection.exists():
    token = secrets.token_urlsafe(48)
    connection.write_text(json.dumps({"url": "https://mcp.example.org/mcp", "token": token}, indent=2), encoding="utf-8")
else:
    token = json.loads(connection.read_text(encoding="utf-8"))["token"]
env_path = private / "memory-mcp.env"
owner_settings = ""
if env_path.exists():
    owner_settings = "".join(line + "\n" for line in env_path.read_text(encoding="utf-8").splitlines()
                             if line.startswith(("MEMORY_USERNAME=", "MEMORY_PASSWORD_HASH=", "MEMORY_VAULT_KEY=")))
env_path.write_text("MEMORY_DATA=/srv/memory-mcp/data\nMEMORY_TOKEN=" + token + "\n" + owner_settings, encoding="utf-8", newline="\n")
(private / "CLAUDE-CONNECTION.txt").write_text(
    "Name: Bash Memory\nMCP server URL: https://mcp.example.org/mcp\n\n"
    "Browser: select Sign in now, then Register automatically under OAuth client. Click Add.\n"
    "Sign in on mcp.example.org using your configured username and password.\n\n"
    "Claude Code is already configured. Its existing request header is:\n"
    "Header name: Authorization\nHeader value: Bearer " + token + "\n\n"
    "The browser uses OAuth; Claude Code can continue using this header.\n"
    "Keep this credential private. Do not paste it into a conversation or commit it to Git.\n",
    encoding="utf-8", newline="\n",
)
print("Private connection files prepared; no credentials printed.")
