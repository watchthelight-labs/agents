"""Best-effort secret scrubbing for inbox text, ported from the library build redaction pass."""

import re

PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.S)),
    ("known-token", re.compile(r"\b(?:sk-(?:ant-|proj-)?[A-Za-z0-9_-]{16,}|ptlc_[A-Za-z0-9]{16,}|(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{15,}|AIza[A-Za-z0-9_-]{25,}|AKIA[A-Z0-9]{16})\b")),
    ("discord-token", re.compile(r"\b(?:[A-Za-z0-9_-]{23,28}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{25,}|mfa\.[A-Za-z0-9_-]{30,})\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("ssn", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")),
    ("authorization", re.compile(r"(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9_+/=.-]{16,}")),
    ("credential-assignment", re.compile(r"""(?im)(["']?(?:\b[\w-]{0,40}(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|secret[_-]?key|session[_-]?token|bot[_-]?token)[\w-]{0,40})["']?\s*[:=]\s*["']?)([^\s"'`,;<>\}\]]{8,})""")),
    ("credential-prose", re.compile(r"(?i)((?:api key|auth token|access token|password|discord token|test token|cloudflare token)\s+(?:is\s+|for you is\s+)?)[A-Za-z0-9_./+!@#$%^&*=-]{16,}")),
    ("url-password", re.compile(r"(?i)(https?://[^\s/:]+:)[^\s/@]+(@)")),
]
KEEP_PREFIX = {"credential-assignment", "credential-prose", "url-password"}
MIN_EXACT = 8


def scrub(text, exact=None):
    """Return (text, counts). `exact` maps literal secret values to a label such as a vault service."""
    counts = {}
    if exact:
        values = sorted((v for v in exact if len(v) >= MIN_EXACT), key=len, reverse=True)
        if values:
            rx = re.compile("|".join(re.escape(v) for v in values))
            def vault_sub(m):
                counts["vault"] = counts.get("vault", 0) + 1
                return "[REDACTED:vault:" + exact[m.group(0)] + "]"
            text = rx.sub(vault_sub, text)
    for label, rx in PATTERNS:
        def sub(m, label=label):
            counts[label] = counts.get(label, 0) + 1
            head = m.group(1) if label in KEEP_PREFIX else ""
            tail = m.group(2) if label == "url-password" else ""
            return head + "[REDACTED:" + label + "]" + tail
        text = rx.sub(sub, text)
    return text, counts
