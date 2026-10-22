import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errMsg, shortId, type Change, type Note, type Receipt } from "./api";

// ---------- toasts ----------

interface Toast {
  id: number;
  text: string;
  kind: "ok" | "err";
}
const ToastCtx = createContext<(text: string, kind?: "ok" | "err") => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);
  const push = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    const id = ++seq.current;
    setToasts((t) => [...t.slice(-3), { id, text, kind }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "err" ? 8000 : 5000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <span>{t.text}</span>
            <button
              className="toast-x"
              aria-label="Dismiss"
              onClick={() => setToasts((all) => all.filter((x) => x.id !== t.id))}
            >
              x
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export const useToast = () => useContext(ToastCtx);

// Shared invalidation after any write.
export function useInvalidate() {
  const qc = useQueryClient();
  return useCallback(
    (noteId?: string) => {
      qc.invalidateQueries({ queryKey: ["overview"] });
      qc.invalidateQueries({ queryKey: ["notes"] });
      qc.invalidateQueries({ queryKey: ["changes"] });
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["threads"] });
      qc.invalidateQueries({ queryKey: ["thread"] });
      qc.invalidateQueries({ queryKey: ["inbox"] });
      if (noteId) qc.invalidateQueries({ queryKey: ["note", noteId] });
      else qc.invalidateQueries({ queryKey: ["note"] });
    },
    [qc],
  );
}

// ---------- markdown ----------

export function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ node: _n, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
          img: ({ node: _n, alt }) => <span className="md-img">[image: {alt || "untitled"}]</span>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

// ---------- small pieces ----------

export function Id({ id }: { id: string }) {
  return (
    <code className="id" title={id}>
      {shortId(id)}
    </code>
  );
}

export function TypeBadge({ type }: { type: string }) {
  return <span className={`badge badge-type t-${type}`}>{type.replace("_", " ")}</span>;
}

export function OpBadge({ op }: { op: string }) {
  return <span className={`badge badge-op op-${op}`}>{op}</span>;
}

export function StaleBadge() {
  return <span className="badge badge-stale">stale</span>;
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return "";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toISOString().slice(0, 10);
}

export function fmtTime(s: string | null | undefined): string {
  if (!s) return "";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function Loading({ what }: { what?: string }) {
  return <p className="muted">Loading{what ? ` ${what}` : ""}...</p>;
}

export function ErrorLine({ error }: { error: unknown }) {
  return <p className="error">{errMsg(error)}</p>;
}

export function NoteLink({ note }: { note: Pick<Note, "note_id" | "title"> }) {
  return <Link to={`/memory/${note.note_id}`}>{note.title || "(untitled)"}</Link>;
}

// ---------- revert ----------

export function RevertButton({ change }: { change: Change }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const [needForce, setNeedForce] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: (force: boolean) => api.revert(change.id, force),
    onSuccess: (r: Receipt) => {
      setNeedForce(null);
      toast(r.receipt);
      invalidate(change.note_id);
    },
    onError: (e) => {
      const msg = errMsg(e);
      if (/later change/i.test(msg)) setNeedForce(msg);
      else toast(msg, "err");
    },
  });
  if (change.reverted_by != null && change.reverted_by !== "") {
    return <span className="muted small">reverted</span>;
  }
  if (needForce) {
    return (
      <span className="force-row">
        <span className="warn small">{needForce}</span>
        <button className="btn btn-danger btn-sm" disabled={m.isPending} onClick={() => m.mutate(true)}>
          Force
        </button>
        <button className="btn btn-sm" onClick={() => setNeedForce(null)}>
          Cancel
        </button>
      </span>
    );
  }
  return (
    <button className="btn btn-sm" disabled={m.isPending} onClick={() => m.mutate(false)}>
      {m.isPending ? "Reverting" : "Revert"}
    </button>
  );
}

export function ChangeRow({
  change,
  showNote = true,
  children,
}: {
  change: Change;
  showNote?: boolean;
  children?: ReactNode;
}) {
  return (
    <li className="change">
      <div className="change-main">
        <OpBadge op={change.op} />
        <span className="change-summary">{change.summary || "(no summary)"}</span>
      </div>
      <div className="change-meta">
        <time className="mono small">{fmtTime(change.ts)}</time>
        {showNote && change.note_id && /^[tpf]:\d+$/.test(change.note_id) ? (
          change.note_id.startsWith("t:") ? (
            <Link className="mono small" to={`/people?thread=${change.note_id.slice(2)}`}>
              {change.note_id}
            </Link>
          ) : (
            <span className="mono small">{change.note_id}</span>
          )
        ) : showNote && change.note_id ? (
          <Link className="mono small" to={`/memory/${change.note_id}`}>
            {shortId(change.note_id)}
          </Link>
        ) : null}
        {(change.surface || change.client_id) && (
          <span className="muted small">
            {[change.surface, change.client_id].filter(Boolean).join(" / ")}
          </span>
        )}
        {change.from_version != null || change.to_version != null ? (
          <span className="muted small mono" title={`${change.from_version ?? "none"} to ${change.to_version ?? "none"}`}>
            {shortId(change.from_version) || "none"} to {shortId(change.to_version) || "none"}
          </span>
        ) : null}
        <RevertButton change={change} />
      </div>
      {children}
    </li>
  );
}
