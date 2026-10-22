"""Encrypted credential vault, kept apart from the searchable archive.

Values are AES-256-GCM ciphertext bound to their row id; only names and field
labels are stored in the clear so credentials can be listed without decrypting.
"""

import base64
from contextlib import contextmanager
import json
from pathlib import Path
import re
import secrets
import sqlite3
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .store import now

SCHEMA = """
CREATE TABLE IF NOT EXISTS credentials (
    id TEXT PRIMARY KEY, service TEXT NOT NULL, label TEXT NOT NULL DEFAULT '',
    project TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]',
    field_names TEXT NOT NULL, secret_fields TEXT NOT NULL DEFAULT '[]',
    source_path TEXT, nonce BLOB NOT NULL, ciphertext BLOB NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version TEXT NOT NULL,
    UNIQUE(project, service, label)
);
CREATE TABLE IF NOT EXISTS credential_audit (
    id INTEGER PRIMARY KEY, ts TEXT NOT NULL, client_id TEXT NOT NULL, action TEXT NOT NULL,
    credential_id TEXT, service TEXT, fields TEXT, reason TEXT
);
"""
SECRET_NAME = re.compile(r"(?i)pass|secret|key|token|\bpin\b|cvv|cvc|private|credential|auth|ssn|seed|recovery|otp|totp")
PUBLIC_NAME = re.compile(r"(?i)\b(?:id|name|email|user(?:name)?|url|ref|domain|server|host|plan|project|region|nameservers?|port)\b$")


def default_secret_fields(names):
    return [n for n in names if SECRET_NAME.search(n) and not PUBLIC_NAME.search(n)]


def load_key(value):
    try:
        key = base64.b64decode(value or "", validate=True)
    except ValueError:
        key = b""
    if len(key) != 32:
        raise ValueError("MEMORY_VAULT_KEY must be 32 bytes, base64-encoded")
    return key


def new_key():
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


class Vault:
    def __init__(self, root, key):
        self.path = Path(root) / "vault.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.aead = AESGCM(load_key(key))
        with self.connection() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(SCHEMA)

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.path, timeout=60)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=60000")
        try:
            with con:
                yield con
        finally:
            con.close()

    def _seal(self, cid, fields):
        nonce = secrets.token_bytes(12)
        return nonce, self.aead.encrypt(nonce, json.dumps(fields, ensure_ascii=False).encode(), cid.encode())

    def _open(self, row):
        return json.loads(self.aead.decrypt(row["nonce"], row["ciphertext"], row["id"].encode()))

    @staticmethod
    def _public(row):
        return {"id": row["id"], "service": row["service"], "label": row["label"], "project": row["project"],
                "tags": json.loads(row["tags"]), "fields": json.loads(row["field_names"]),
                "secret_fields": json.loads(row["secret_fields"]), "source_path": row["source_path"],
                "updated_at": row["updated_at"], "version": row["version"]}

    def _audit(self, con, client_id, action, row, fields=None, reason=None):
        con.execute("INSERT INTO credential_audit(ts,client_id,action,credential_id,service,fields,reason) VALUES (?,?,?,?,?,?,?)",
                    (now(), client_id or "unknown", action, row["id"] if row else None, row["service"] if row else None,
                     json.dumps(fields) if fields else None, reason))

    def count(self):
        with self.connection() as con:
            return con.execute("SELECT count(*) FROM credentials").fetchone()[0]

    def list(self, query=None, project=None, limit=100):
        clauses, params = [], []
        for word in re.findall(r"[^\W_]+", query or "", re.UNICODE)[:8]:
            clauses.append("(service||' '||label||' '||project||' '||tags||' '||field_names) LIKE ? ESCAPE '\\'")
            params.append("%" + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        if project:
            clauses.append("project=?")
            params.append(project)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self.connection() as con:
            rows = con.execute("SELECT * FROM credentials" + where + " ORDER BY project,service,label LIMIT ?", params + [limit]).fetchall()
        return {"credentials": [self._public(r) for r in rows],
                "guidance": "Names only. Call get_credential with an id and a reason when a task needs the values."}

    def _resolve(self, con, ref, project=None):
        if re.fullmatch(r"[a-f0-9]{32}", ref):
            row = con.execute("SELECT * FROM credentials WHERE id=?", (ref,)).fetchone()
            if row:
                return row
        params = [ref, ref]
        sql = "SELECT * FROM credentials WHERE (lower(service)=lower(?) OR lower(service||' / '||label)=lower(?))"
        if project:
            sql += " AND project=?"
            params.append(project)
        rows = con.execute(sql + " LIMIT 20", params).fetchall()
        if len(rows) == 1:
            return rows[0]
        if not rows:
            raise ValueError("No credential matches; use list_credentials to find its id")
        raise ValueError("Ambiguous credential reference; use one of these ids: " +
                         ", ".join(f"{r['id']} ({r['project']}: {r['service']} / {r['label']})" for r in rows))

    def get(self, ref, fields=None, reason="", client_id=None, project=None):
        if not reason.strip():
            raise ValueError("State the reason this task needs the credential")
        with self.connection() as con:
            row = self._resolve(con, ref, project)
            values = self._open(row)
            if fields:
                missing = [f for f in fields if f not in values]
                if missing:
                    raise ValueError("Unknown fields: " + ", ".join(missing) + "; available: " + ", ".join(values))
                values = {f: values[f] for f in fields}
            self._audit(con, client_id, "get", row, list(values), reason[:500])
        return {**self._public(row), "values": values,
                "guidance": "Use these values only for the task stated in the reason. Do not repeat them in chat unless the user asked to see them."}

    def put(self, service, fields, label="", project="", tags=None, secret_fields=None, source_path=None,
            cred_id=None, expected_version=None, client_id=None, upsert=False):
        if not service.strip() or len(service) > 200 or len(label) > 200 or len(project) > 200:
            raise ValueError("A credential needs a service name (1-200 characters)")
        if not isinstance(fields, dict) or not fields or not all(isinstance(k, str) and isinstance(v, str) for k, v in fields.items()):
            raise ValueError("fields must be a non-empty object of string names to string values")
        names = list(fields)
        secret = default_secret_fields(names) if secret_fields is None else [n for n in secret_fields if n in fields]
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            if cred_id is not None:
                row = con.execute("SELECT * FROM credentials WHERE id=?", (cred_id,)).fetchone()
                if not row:
                    raise ValueError("Credential not found")
            else:
                row = con.execute("SELECT * FROM credentials WHERE project=? AND service=? AND label=?", (project, service, label)).fetchone()
                if row and not upsert and expected_version is None:
                    raise ValueError(f"Credential already exists (id {row['id']}); pass id and expected_version to replace it")
            if row and not upsert and row["version"] != expected_version:
                raise ValueError("Version conflict: list the credential again before updating")
            cid = row["id"] if row else uuid.uuid4().hex
            nonce, ciphertext = self._seal(cid, fields)
            version = secrets.token_hex(8)
            stamp = now()
            con.execute("""INSERT INTO credentials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET service=excluded.service,label=excluded.label,project=excluded.project,
                tags=excluded.tags,field_names=excluded.field_names,secret_fields=excluded.secret_fields,
                source_path=excluded.source_path,nonce=excluded.nonce,ciphertext=excluded.ciphertext,
                updated_at=excluded.updated_at,version=excluded.version""",
                (cid, service, label, project, json.dumps(tags or []), json.dumps(names), json.dumps(secret),
                 source_path, nonce, ciphertext, row["created_at"] if row else stamp, stamp, version))
            saved = con.execute("SELECT * FROM credentials WHERE id=?", (cid,)).fetchone()
            self._audit(con, client_id, "update" if row else "create", saved, names)
        return {**self._public(saved), "created": not row}

    def delete(self, cred_id, expected_version, client_id=None, reason=None):
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM credentials WHERE id=?", (cred_id,)).fetchone()
            if not row:
                raise ValueError("Credential not found")
            if row["version"] != expected_version:
                raise ValueError("Version conflict: list the credential again before deleting")
            con.execute("DELETE FROM credentials WHERE id=?", (cred_id,))
            self._audit(con, client_id, "delete", row, None, reason)
        return {"deleted": cred_id, "service": row["service"], "label": row["label"]}

    def audit(self, limit=50):
        with self.connection() as con:
            rows = con.execute("SELECT * FROM credential_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return {"events": [{**dict(r), "fields": json.loads(r["fields"]) if r["fields"] else None} for r in rows]}

    def secret_values(self):
        """Exact secret values mapped to their service, for scrubbing archive imports."""
        found = {}
        with self.connection() as con:
            for row in con.execute("SELECT * FROM credentials").fetchall():
                values = self._open(row)
                for name in json.loads(row["secret_fields"]):
                    value = values.get(name, "")
                    # Token-like values only; prose such as "20 req/min" or long notes would over-redact archive text.
                    # Paths, URLs without embedded passwords, and bare numeric IDs are references, not secrets.
                    if (8 <= len(value) <= 4096 and not re.search(r"\s", value) and not value.isalpha()
                            and not value.isdigit() and not re.match(r"(?i)^(?:[a-z]:[\\/]|~?/|\.{1,2}[\\/])", value)
                            and not re.match(r"(?i)^https?://[^@]*$", value)):
                        found[value] = row["service"]
        return found
