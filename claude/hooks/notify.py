#!/usr/bin/env python3
"""Desktop / phone notifier for the hooks. Config: ~/.claude/notify.json.

Backends: Windows toast (powershell.exe 5.1 + WinRT, no modules needed) and
ntfy (any ntfy.sh-compatible topic URL). `python notify.py --test` fires one.
"""

import json, os, subprocess, sys, tempfile, time, urllib.request
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cchooks as H  # noqa: E402

CONFIG = os.path.join(H.CLAUDE_DIR, "notify.json")
DEFAULTS = {
    "toast": True,
    "toast_sound": True,
    "ntfy": {"url": "", "token": "", "priority": "default"},
    "min_turn_secs": 120,
    "always_if_agents": True,
    "needs_input_types": ["permission_prompt", "idle_prompt", "agent_needs_input",
                          "elicitation_dialog"],
    "needs_input_cooldown": 60,
}
# AUMID of Windows PowerShell: a registered app id, so the toast actually shows.
PS_AUMID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
PS_EXE = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                      "System32", "WindowsPowerShell", "v1.0", "powershell.exe")


def config():
    cfg = dict(DEFAULTS)
    user = H.load_json(CONFIG, {})
    if isinstance(user, dict):
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k] = {**cfg[k], **v}
            else:
                cfg[k] = v
    return cfg


def toast(title, body, sound=True, wait=False):
    """Windows toast via WinRT from powershell.exe 5.1 (pwsh 7 lacks the
    WinRT projection). Spawned detached so the hook returns at once."""
    if sys.platform != "win32" or not os.path.isfile(PS_EXE):
        return False
    audio = "" if sound else '<audio silent="true"/>'
    xml = (f"<toast><visual><binding template='ToastGeneric'>"
           f"<text>{escape(title)}</text><text>{escape(body)}</text>"
           f"</binding></visual>{audio}</toast>")
    fd, path = tempfile.mkstemp(prefix="cltoast-", suffix=".xml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(xml)
    ps = (
        f"$p='{path}';"
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
        "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
        "$x.LoadXml([System.IO.File]::ReadAllText($p, [System.Text.Encoding]::UTF8));"
        "$n = [Windows.UI.Notifications.ToastNotification]::new($x);"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{PS_AUMID}').Show($n);"
        "Start-Sleep -Milliseconds 800; Remove-Item $p -ErrorAction SilentlyContinue"
    )
    args = [PS_EXE, "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass", "-Command", ps]
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
             | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if wait:
        r = subprocess.run(args, capture_output=True, text=True, timeout=20,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            sys.stderr.write(r.stderr[-800:])
        return r.returncode == 0
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags)
    return True


def ntfy(title, body, cfg):
    n = cfg.get("ntfy") or {}
    url = (n.get("url") or "").strip()
    if not url:
        return False
    req = urllib.request.Request(url, data=body.encode("utf-8"), method="POST")
    req.add_header("Title", title.encode("ascii", "ignore").decode())
    req.add_header("Priority", str(n.get("priority") or "default"))
    req.add_header("Tags", "robot")
    if n.get("token"):
        req.add_header("Authorization", f"Bearer {n['token']}")
    with urllib.request.urlopen(req, timeout=6):
        return True


def send(title, body, cfg=None, wait=False):
    cfg = cfg or config()
    sent = False
    if cfg.get("toast", True):
        try:
            sent = toast(title, body, bool(cfg.get("toast_sound", True)), wait) or sent
        except Exception as e:
            if wait:
                sys.stderr.write(f"toast failed: {e}\n")
    try:
        sent = ntfy(title, body, cfg) or sent
    except Exception as e:
        if wait:
            sys.stderr.write(f"ntfy failed: {e}\n")
    return sent


if __name__ == "__main__":
    if "--test" in sys.argv:
        ok = send("Claude Code", f"notify.py test at {time.strftime('%H:%M:%S')}", wait=True)
        print("sent" if ok else "nothing sent (check notify.json)")
        sys.exit(0 if ok else 1)
    if len(sys.argv) >= 3:
        sys.exit(0 if send(sys.argv[1], " ".join(sys.argv[2:]), wait=True) else 1)
    print(__doc__)
