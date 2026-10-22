// Typed client for the dashboard API. Same-origin only.

export type NoteType =
  | "preference"
  | "fact"
  | "runbook"
  | "decision"
  | "gotcha"
  | "open_loop"
  | "session_digest";

export const NOTE_TYPES: NoteType[] = [
  "preference",
  "fact",
  "runbook",
  "decision",
  "gotcha",
  "open_loop",
  "session_digest",
];

export interface Note {
  note_id: string;
  title: string;
  current_version: string; // document id (hash) of the current version
  type: NoteType | string;
  scope: string;
  sensitivity: string;
  status: "active" | "archived" | string;
  pinned: number;
  verified_at: string | null;
  review_by: string | null;
  supersedes: string | null;
  origin: string | null;
  created_at: string;
  updated_at: string;
  stale: boolean;
}

export interface Change {
  id: number | string;
  ts: string;
  note_id: string;
  op: string;
  from_version: string | null;
  to_version: string | null;
  before_meta: unknown;
  after_meta: unknown;
  surface: string | null;
  client_id: string | null;
  summary: string | null;
  reverted_by: number | string | null;
}

export interface NoteDetail extends Note {
  evidence_type: string | null;
  source_date: string | null;
  source_reference: string | null;
  content: string;
  history: Change[];
}

export interface Project {
  key: string;
  title: string;
  summary: string;
  path_globs: string[];
  git_remotes: string[];
  aliases: string[];
  active_notes: number;
  created_at: string;
  updated_at: string;
}

export interface Status {
  sources: number;
  by_kind: Record<string, number>;
  passages: number;
  notes: { active: number; archived: number };
  projects: number;
  changes: number;
  ingestion_complete: boolean;
  ingestion_by_namespace: Record<string, unknown>;
}

export interface Overview {
  status: Status;
  open_loops: Note[];
  stale: Note[];
  recent_changes: Change[];
  projects: Project[];
}

export interface Me {
  email: string;
  csrf: string;
}

export interface DuplicateCandidate {
  note_id: string;
  version: string;
  title: string;
  type: string;
  excerpt: string;
  score: number;
}

export type RememberResult =
  | {
      status: "saved";
      note_id: string;
      version: string;
      change_id: number | string;
      receipt: string;
      redacted: unknown;
    }
  | { status: "possible_duplicate"; candidates: DuplicateCandidate[]; hint: string };

export interface Receipt {
  note_id?: string;
  change_id: number | string;
  receipt: string;
}

export interface BootResult {
  project: Project | null;
  parts: { profile: string; project: string; threads: string };
}

export interface SearchResult {
  document_id: string;
  ordinal: number;
  excerpt: string;
  source: string;
  title: string;
  kind: string;
  source_date: string | null;
  note_type?: string;
  note_scope?: string;
}

export interface SourcePage {
  document_id: string;
  current_sources: { uri: string; title: string; kind: string }[];
  total_chunks: number;
  passages: { ordinal: number; start_char: number; end_char: number; text: string }[];
  next_chunk: number | null;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let csrfToken: string | null = null;
let mePromise: Promise<Me> | null = null;

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  if (!res.ok) {
    const msg =
      body && typeof body === "object" && "error" in body
        ? String((body as { error: unknown }).error)
        : `Request failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return body as T;
}

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    p.set(k, v === true ? "1" : String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  return parse<T>(res);
}

async function send<T>(method: "POST" | "PUT" | "PATCH", path: string, body?: unknown): Promise<T> {
  if (!csrfToken) await getMe();
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRF": csrfToken ?? "",
    },
    body: JSON.stringify(body ?? {}),
  });
  return parse<T>(res);
}

const enc = encodeURIComponent;

export function getMe(): Promise<Me> {
  if (!mePromise) {
    mePromise = get<Me>("/api/me").then(
      (me) => {
        csrfToken = me.csrf;
        return me;
      },
      (err) => {
        mePromise = null;
        throw err;
      },
    );
  }
  return mePromise;
}

export interface NoteFilters {
  type?: string;
  scope?: string;
  status?: "active" | "archived";
  stale?: boolean;
  q?: string;
  limit?: number;
  offset?: number;
}

export const api = {
  me: getMe,
  overview: () => get<Overview>("/api/overview"),
  notes: (f: NoteFilters) =>
    get<{ total: number; notes: Note[] }>(`/api/notes${qs({ ...f })}`),
  note: (id: string) => get<NoteDetail>(`/api/notes/${enc(id)}`),
  noteVersion: (id: string, documentId: string) =>
    get<{ content: string }>(`/api/notes/${enc(id)}/versions/${enc(documentId)}`),
  createNote: (b: {
    title: string;
    content: string;
    type: string;
    scope: string;
    force_new?: boolean;
    sensitivity?: string;
    pinned?: boolean;
  }) => send<RememberResult>("POST", "/api/notes", b),
  updateNote: (
    id: string,
    b: { title: string; content: string; type: string; scope: string; expected_version: string },
  ) => send<RememberResult>("PUT", `/api/notes/${enc(id)}`, b),
  verify: (id: string) => send<Receipt>("POST", `/api/notes/${enc(id)}/verify`),
  archive: (id: string, reason: string) =>
    send<Receipt>("POST", `/api/notes/${enc(id)}/archive`, { reason }),
  restore: (id: string) => send<Receipt>("POST", `/api/notes/${enc(id)}/restore`),
  relabel: (
    id: string,
    b: {
      type?: string;
      scope?: string;
      sensitivity?: string;
      pinned?: boolean;
      review_by?: string | null;
    },
  ) => send<Receipt>("PATCH", `/api/notes/${enc(id)}/labels`, b),
  changes: (f: { since?: string; note_id?: string; limit?: number }) =>
    get<{ changes: Change[] }>(`/api/changes${qs({ ...f })}`),
  revert: (changeId: number | string, force = false) =>
    send<Receipt>("POST", `/api/changes/${enc(String(changeId))}/revert`, force ? { force: true } : {}),
  projects: () => get<{ projects: Project[] }>("/api/projects"),
  updateProject: (
    key: string,
    b: {
      title?: string;
      summary?: string;
      path_globs?: string[];
      git_remotes?: string[];
      aliases?: string[];
    },
  ) => send<Project>("PUT", `/api/projects/${enc(key)}`, b),
  boot: (p: { cwd?: string; project?: string }) => get<BootResult>(`/api/boot${qs(p)}`),
  search: (p: { q: string; mode: "all" | "any"; kind?: string; archived?: boolean }) =>
    get<{ results: SearchResult[] }>(`/api/search${qs(p)}`),
  source: (documentId: string, start: number, count = 2) =>
    get<SourcePage>(`/api/source/${enc(documentId)}${qs({ start: String(start), count })}`),
};

export function shortId(id: string | null | undefined): string {
  return id ? id.slice(0, 8) : "";
}

export function errMsg(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}
