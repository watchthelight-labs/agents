"""JSON API behind dash.example.org. nginx serves the SPA; this app answers /api/* on 127.0.0.1.

Every request is authenticated by Cloudflare Access (see access.py). Writes also need the page's own Origin and
an X-CSRF token derived from the signed-in email, and go through Memory with surface='dashboard'.
"""

import hmac
import json
import os
from pathlib import Path

import anyio
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from ..contacts import Contacts
from ..memory import PARTS, Memory
from ..store import Store
from .access import AccessError, AccessVerifier, DevVerifier, csrf_token, new_secret

NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
MAX_BODY = 256 * 1024


def error(message, status):
    return JSONResponse({"error": message}, status_code=status, headers=NO_STORE)


def status_for(exc):
    text = str(exc).lower()
    if "conflict" in text or "later changes" in text or "already reverted" in text:
        return 409
    if "not found" in text or "no note matches" in text or "unknown project" in text or "no thread" in text or "no such" in text:
        return 404
    return 400


def create_dash(data_dir, verifier=None, origins=None, secret=None):
    store = Store(Path(data_dir))
    memory = Memory(store)  # No vault here: the dashboard never holds the vault key in v0b.
    contacts = Contacts(store, memory)
    if verifier is None:
        if os.environ.get("DASH_DEV") == "1":
            verifier = DevVerifier()
        else:
            verifier = AccessVerifier(os.environ.get("CF_TEAM_DOMAIN"), os.environ.get("CF_ACCESS_AUD"),
                                      os.environ.get("OWNER_EMAIL"))
    origins = set(origins or os.environ.get("DASH_ORIGINS", "https://dash.example.org").split(","))
    secret = secret or (bytes.fromhex(os.environ["DASH_SECRET"]) if os.environ.get("DASH_SECRET") else new_secret())

    def endpoint(fn, write=False):
        async def handler(request: Request):
            try:
                email = verifier.verify(request.headers.get("cf-access-jwt-assertion", ""))
            except AccessError as exc:
                return error(str(exc), 403)
            if write:
                if request.headers.get("origin") not in origins:
                    return error("Writes must come from the dashboard page", 403)
                if not hmac.compare_digest(request.headers.get("x-csrf", ""), csrf_token(secret, email)):
                    return error("Missing or stale CSRF token; reload the page", 403)
            body = {}
            if request.method in ("POST", "PUT", "PATCH"):
                raw = await request.body()
                if len(raw) > MAX_BODY:
                    return error("Request too large", 413)
                if raw:
                    try:
                        body = json.loads(raw)
                    except ValueError:
                        return error("Body must be JSON", 400)
                    if not isinstance(body, dict):
                        return error("Body must be a JSON object", 400)
            try:
                result = await anyio.to_thread.run_sync(lambda: fn(request, body, email))
            except ValueError as exc:
                return error(str(exc), status_for(exc))
            except (KeyError, TypeError) as exc:
                return error(f"Bad request: {exc}", 400)
            return JSONResponse(result, headers=NO_STORE)
        return handler

    q = lambda request, key, default=None: request.query_params.get(key) or default  # noqa: E731
    nid = lambda request: memory.resolve_id(request.path_params["note_id"])  # noqa: E731

    def me(request, body, email):
        return {"email": email, "csrf": csrf_token(secret, email)}

    def overview(request, body, email):
        return {"status": {k: v for k, v in store.status().items() if k not in ("recent_imports", "search", "privacy")},
                "open_loops": memory.list_notes(type="open_loop", limit=50)["notes"],
                "stale": memory.list_notes(stale=True, limit=50)["notes"],
                "recent_changes": memory.list_changes(limit=20)["changes"],
                "projects": memory.list_projects()["projects"],
                "contacts": contacts.counts(trusted=True)}

    def threads(request, body, email):
        return contacts.list_threads(None, None, q(request, "state", "active"), q(request, "platform"), q(request, "project"),
                                     q(request, "person"), q(request, "q"), int(q(request, "limit", 100)))

    def thread(request, body, email):
        return contacts.list_threads(request.path_params["thread_id"])

    def update_thread(request, body, email):
        allowed = {"why", "stance", "state", "project", "title", "sensitivity", "next_check_days", "summary", "direction", "who"}
        extra = set(body) - allowed
        if extra:
            raise ValueError("Unknown fields: " + ", ".join(sorted(extra)))
        return contacts.log_contact(thread_id=request.path_params["thread_id"], surface="dashboard", client_id=email,
                                    follow=False, **body)

    def inbox(request, body, email):
        return contacts.inbox(int(q(request, "limit", 50)), q(request, "releases") in ("1", "true"))

    def seen(request, body, email):
        return contacts.mark_seen(body.get("event_ids"), body.get("thread_id"), body.get("snooze_days"), "dashboard", email)

    def forget_person(request, body, email):
        return contacts.forget_person(body["handle"], "dashboard", email)

    def notes(request, body, email):
        return memory.list_notes(q(request, "type"), q(request, "scope"), q(request, "status", "active"),
                                 q(request, "stale") in ("1", "true"), q(request, "q"),
                                 int(q(request, "limit", 100)), int(q(request, "offset", 0)))

    def create_note(request, body, email):
        return memory.remember(body["title"], body["content"], body["type"], body.get("scope", "global"),
                               sensitivity=body.get("sensitivity", "normal"), pinned=body.get("pinned"),
                               force_new=bool(body.get("force_new")), surface="dashboard", client_id=email)

    def note(request, body, email):
        return memory.get_note(nid(request))

    def update_note(request, body, email):
        note_id = nid(request)
        current = memory.get_note(note_id)
        return memory.remember(body.get("title", current["title"]), body.get("content", current["content"]),
                               body.get("type", current["type"]), body.get("scope", current["scope"]),
                               note_id, body["expected_version"], sensitivity=body.get("sensitivity", current["sensitivity"]),
                               pinned=body.get("pinned"), surface="dashboard", client_id=email)

    def version(request, body, email):
        return {"content": memory.version_text(nid(request), request.path_params["document_id"])}

    def verify(request, body, email):
        return memory.verify_note(nid(request), "dashboard", email)

    def archive(request, body, email):
        return memory.archive_note(nid(request), str(body.get("reason", ""))[:200], "dashboard", email)

    def restore(request, body, email):
        return memory.restore_note(nid(request), "dashboard", email)

    def labels(request, body, email):
        fields = {k: body.get(k) for k in ("type", "scope", "sensitivity", "pinned", "review_by")}
        return memory.set_meta(nid(request), "dashboard", email, **fields)

    def changes(request, body, email):
        note_id = q(request, "note_id")
        return memory.list_changes(q(request, "since"), int(q(request, "limit", 100)),
                                   memory.resolve_id(note_id) if note_id else None)

    def revert(request, body, email):
        return memory.revert_change(int(request.path_params["change_id"]), "dashboard", email, None, bool(body.get("force")))

    def projects(request, body, email):
        return memory.list_projects()

    def update_project(request, body, email):
        return memory.set_project(request.path_params["key"], body.get("title"), body.get("summary"),
                                  body.get("path_globs"), body.get("git_remotes"), body.get("aliases"))

    def boot(request, body, email):
        cwd, project = q(request, "cwd"), q(request, "project")
        match = memory.resolve_project(cwd, None, project)
        parts = {p: memory.boot(p, cwd, None, project, "dashboard", include_infra=False) for p in PARTS if p != "infra"}
        return {"project": match, "parts": parts}

    def search(request, body, email):
        query = q(request, "q", "")
        kind = q(request, "kind")
        return store.search(query, 20, kind, None, q(request, "mode", "all"), False, None, None,
                            q(request, "archived") in ("1", "true"), True)

    def source(request, body, email):
        return store.read(request.path_params["document_id"], int(q(request, "start", 0)), int(q(request, "count", 2)))

    routes = [
        Route("/api/me", endpoint(me)),
        Route("/api/overview", endpoint(overview)),
        Route("/api/notes", endpoint(notes), methods=["GET"]),
        Route("/api/notes", endpoint(create_note, True), methods=["POST"]),
        Route("/api/notes/{note_id}", endpoint(note), methods=["GET"]),
        Route("/api/notes/{note_id}", endpoint(update_note, True), methods=["PUT"]),
        Route("/api/notes/{note_id}/versions/{document_id}", endpoint(version)),
        Route("/api/notes/{note_id}/verify", endpoint(verify, True), methods=["POST"]),
        Route("/api/notes/{note_id}/archive", endpoint(archive, True), methods=["POST"]),
        Route("/api/notes/{note_id}/restore", endpoint(restore, True), methods=["POST"]),
        Route("/api/notes/{note_id}/labels", endpoint(labels, True), methods=["PATCH"]),
        Route("/api/changes", endpoint(changes)),
        Route("/api/changes/{change_id:int}/revert", endpoint(revert, True), methods=["POST"]),
        Route("/api/projects", endpoint(projects)),
        Route("/api/projects/{key}", endpoint(update_project, True), methods=["PUT"]),
        Route("/api/boot", endpoint(boot)),
        Route("/api/threads", endpoint(threads)),
        Route("/api/threads/{thread_id:int}", endpoint(thread), methods=["GET"]),
        Route("/api/threads/{thread_id:int}", endpoint(update_thread, True), methods=["PATCH"]),
        Route("/api/inbox", endpoint(inbox)),
        Route("/api/inbox/seen", endpoint(seen, True), methods=["POST"]),
        Route("/api/people/forget", endpoint(forget_person, True), methods=["POST"]),
        Route("/api/search", endpoint(search)),
        Route("/api/source/{document_id}", endpoint(source)),
    ]
    app = Starlette(routes=routes)

    async def not_found(request, exc):
        return error("Not found", 404)

    app.add_exception_handler(404, not_found)
    app.add_exception_handler(405, lambda request, exc: error("Method not allowed", 405))
    return app
