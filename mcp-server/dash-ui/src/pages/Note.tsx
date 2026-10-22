import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, ApiError, errMsg, NOTE_TYPES, shortId, type Change, type NoteDetail, type Receipt } from "../api";
import { lineDiff } from "../diff";
import {
  ChangeRow,
  ErrorLine,
  Id,
  Loading,
  Markdown,
  StaleBadge,
  TypeBadge,
  fmtDate,
  fmtTime,
  useInvalidate,
  useToast,
} from "../ui";

export const SENSITIVITIES = ["normal", "private"];

export function NotePage() {
  const { id = "" } = useParams();
  const q = useQuery({ queryKey: ["note", id], queryFn: () => api.note(id), enabled: !!id });
  if (q.isPending) return <Loading what="note" />;
  if (q.isError) return <ErrorLine error={q.error} />;
  return <NoteView note={q.data} reload={() => q.refetch()} />;
}

type Mode = "view" | "edit" | "relabel" | "archive";

function NoteView({ note, reload }: { note: NoteDetail; reload: () => void }) {
  const [mode, setMode] = useState<Mode>("view");
  const toast = useToast();
  const invalidate = useInvalidate();
  const done = (r: { receipt: string }) => {
    toast(r.receipt);
    invalidate(note.note_id);
    setMode("view");
  };
  const fail = (e: unknown) => toast(errMsg(e), "err");

  const verify = useMutation({ mutationFn: () => api.verify(note.note_id), onSuccess: done, onError: fail });
  const restore = useMutation({ mutationFn: () => api.restore(note.note_id), onSuccess: done, onError: fail });
  const archived = note.status === "archived";

  return (
    <article className="stack">
      <div className="crumbs small">
        <Link to="/memory">Memory</Link> / <Id id={note.note_id} />
      </div>
      <h1 className="note-title">{note.title || "(untitled)"}</h1>
      <div className="labels">
        <TypeBadge type={note.type} />
        <Link className="badge badge-scope" to={`/memory?scope=${encodeURIComponent(note.scope)}`}>
          {note.scope}
        </Link>
        <span className={`badge sens-${note.sensitivity}`}>{note.sensitivity}</span>
        {note.pinned ? <span className="badge badge-pin">pinned</span> : null}
        {archived ? <span className="badge badge-archived">archived</span> : null}
        {note.stale ? <StaleBadge /> : null}
        <span className="label-kv">
          verified <b className="mono">{fmtDate(note.verified_at) || "never"}</b>
        </span>
        <span className={`label-kv${note.stale ? " warn" : ""}`}>
          review by <b className="mono">{fmtDate(note.review_by) || "unset"}</b>
        </span>
        <span className="label-kv" title={note.current_version}>
          version <b className="mono">{shortId(note.current_version)}</b>
        </span>
      </div>

      <div className="actions">
        <button className={`btn${mode === "edit" ? " on" : ""}`} onClick={() => setMode(mode === "edit" ? "view" : "edit")}>
          Edit
        </button>
        <button className="btn" disabled={verify.isPending} onClick={() => verify.mutate()}>
          Verify
        </button>
        <button
          className={`btn${mode === "relabel" ? " on" : ""}`}
          onClick={() => setMode(mode === "relabel" ? "view" : "relabel")}
        >
          Relabel
        </button>
        {archived ? (
          <button className="btn" disabled={restore.isPending} onClick={() => restore.mutate()}>
            Restore
          </button>
        ) : (
          <button
            className={`btn btn-danger${mode === "archive" ? " on" : ""}`}
            onClick={() => setMode(mode === "archive" ? "view" : "archive")}
          >
            Archive
          </button>
        )}
      </div>

      {mode === "archive" && <ArchiveForm note={note} onDone={done} onCancel={() => setMode("view")} />}
      {mode === "relabel" && <RelabelForm note={note} onDone={done} onCancel={() => setMode("view")} />}
      {mode === "edit" ? (
        <EditForm note={note} onDone={done} onCancel={() => setMode("view")} reload={reload} />
      ) : (
        <section className="panel">
          <Markdown text={note.content} />
        </section>
      )}

      <dl className="meta small">
        <dt>created</dt>
        <dd className="mono">{fmtTime(note.created_at)}</dd>
        <dt>updated</dt>
        <dd className="mono">{fmtTime(note.updated_at)}</dd>
        {note.origin ? (
          <>
            <dt>origin</dt>
            <dd>{note.origin}</dd>
          </>
        ) : null}
        {note.evidence_type ? (
          <>
            <dt>evidence</dt>
            <dd>{note.evidence_type}</dd>
          </>
        ) : null}
        {note.source_date ? (
          <>
            <dt>source date</dt>
            <dd className="mono">{fmtDate(note.source_date)}</dd>
          </>
        ) : null}
        {note.source_reference ? (
          <>
            <dt>source</dt>
            <dd className="mono wrap">{note.source_reference}</dd>
          </>
        ) : null}
        {note.supersedes ? (
          <>
            <dt>supersedes</dt>
            <dd>
              <Link className="mono" to={`/memory/${note.supersedes}`}>
                {shortId(note.supersedes)}
              </Link>
            </dd>
          </>
        ) : null}
      </dl>

      <History note={note} />
    </article>
  );
}

function EditForm({
  note,
  onDone,
  onCancel,
  reload,
}: {
  note: NoteDetail;
  onDone: (r: { receipt: string }) => void;
  onCancel: () => void;
  reload: () => void;
}) {
  const toast = useToast();
  const [title, setTitle] = useState(note.title);
  const [content, setContent] = useState(note.content);
  const [conflict, setConflict] = useState(false);
  const m = useMutation({
    mutationFn: () =>
      api.updateNote(note.note_id, {
        title,
        content,
        type: note.type,
        scope: note.scope,
        expected_version: note.current_version,
      }),
    onSuccess: (r) => {
      if (r.status === "saved") onDone(r);
      else toast(r.hint || "Looks like a duplicate. Not saved.", "err");
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) setConflict(true);
      else toast(errMsg(e), "err");
    },
  });
  return (
    <form
      className="panel form"
      onSubmit={(e) => {
        e.preventDefault();
        m.mutate();
      }}
    >
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} required />
      </label>
      <label>
        Content
        <textarea rows={Math.min(40, Math.max(10, content.split("\n").length + 2))} value={content} onChange={(e) => setContent(e.target.value)} />
      </label>
      {conflict ? (
        <p className="warn">
          Changed elsewhere since you opened it.{" "}
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              setConflict(false);
              reload();
              onCancel();
            }}
          >
            Reload
          </button>
        </p>
      ) : null}
      <div className="actions">
        <button className="btn btn-primary" disabled={m.isPending}>
          {m.isPending ? "Saving" : "Save"}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function ArchiveForm({
  note,
  onDone,
  onCancel,
}: {
  note: NoteDetail;
  onDone: (r: Receipt) => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const m = useMutation({
    mutationFn: () => api.archive(note.note_id, reason.trim()),
    onSuccess: onDone,
    onError: (e) => toast(errMsg(e), "err"),
  });
  return (
    <form
      className="panel form panel-danger"
      onSubmit={(e) => {
        e.preventDefault();
        m.mutate();
      }}
    >
      <label>
        Why archive it?
        <input value={reason} onChange={(e) => setReason(e.target.value)} required autoFocus />
      </label>
      <div className="actions">
        <button className="btn btn-danger" disabled={m.isPending || !reason.trim()}>
          Archive
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function RelabelForm({
  note,
  onDone,
  onCancel,
}: {
  note: NoteDetail;
  onDone: (r: Receipt) => void;
  onCancel: () => void;
}) {
  const toast = useToast();
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const [type, setType] = useState(note.type);
  const [scope, setScope] = useState(note.scope);
  const [sensitivity, setSensitivity] = useState(note.sensitivity);
  const [pinned, setPinned] = useState(!!note.pinned);
  const [reviewBy, setReviewBy] = useState(note.review_by ? note.review_by.slice(0, 10) : "");
  const m = useMutation({
    mutationFn: () => {
      const b: Parameters<typeof api.relabel>[1] = {};
      if (type !== note.type) b.type = type;
      if (scope !== note.scope) b.scope = scope;
      if (sensitivity !== note.sensitivity) b.sensitivity = sensitivity;
      if (pinned !== !!note.pinned) b.pinned = pinned;
      if (reviewBy !== (note.review_by ? note.review_by.slice(0, 10) : "")) b.review_by = reviewBy || null;
      return api.relabel(note.note_id, b);
    },
    onSuccess: onDone,
    onError: (e) => toast(errMsg(e), "err"),
  });
  const scopes = ["global", ...(projects.data?.projects.map((p) => `project:${p.key}`) ?? [])];
  if (!scopes.includes(note.scope)) scopes.push(note.scope);
  const sens = SENSITIVITIES.includes(note.sensitivity) ? SENSITIVITIES : [...SENSITIVITIES, note.sensitivity];
  return (
    <form
      className="panel form grid-form"
      onSubmit={(e) => {
        e.preventDefault();
        m.mutate();
      }}
    >
      <label>
        Type
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {NOTE_TYPES.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      </label>
      <label>
        Scope
        <select value={scope} onChange={(e) => setScope(e.target.value)}>
          {scopes.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </label>
      <label>
        Sensitivity
        <select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)}>
          {sens.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </label>
      <label>
        Review by
        <input type="date" value={reviewBy} onChange={(e) => setReviewBy(e.target.value)} />
      </label>
      <label className="check">
        <input type="checkbox" checked={pinned} onChange={(e) => setPinned(e.target.checked)} />
        pinned
      </label>
      <div className="actions span-all">
        <button className="btn btn-primary" disabled={m.isPending}>
          Save labels
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function History({ note }: { note: NoteDetail }) {
  const [open, setOpen] = useState<Change | null>(null);
  const history = [...note.history].sort((a, b) => (a.ts < b.ts ? 1 : -1));
  return (
    <section className="panel">
      <h2>History</h2>
      {history.length ? (
        <ul className="changes">
          {history.map((c) => (
            <ChangeRow key={c.id} change={c} showNote={false}>
              {c.to_version && c.to_version !== note.current_version ? (
                <button className="btn-link small" onClick={() => setOpen(open?.id === c.id ? null : c)}>
                  {open?.id === c.id ? "Hide this version" : "View this version"}
                </button>
              ) : c.to_version ? (
                <span className="muted small">current version</span>
              ) : null}
              {open?.id === c.id && c.to_version ? (
                <VersionDiff noteId={note.note_id} documentId={c.to_version} current={note.content} />
              ) : null}
            </ChangeRow>
          ))}
        </ul>
      ) : (
        <p className="muted">No history.</p>
      )}
    </section>
  );
}

function VersionDiff({ noteId, documentId, current }: { noteId: string; documentId: string; current: string }) {
  const q = useQuery({
    queryKey: ["version", noteId, documentId],
    queryFn: () => api.noteVersion(noteId, documentId),
    staleTime: Infinity,
  });
  if (q.isPending) return <Loading what="version" />;
  if (q.isError) return <ErrorLine error={q.error} />;
  const lines = lineDiff(q.data.content, current);
  const changed = lines.filter((l) => l.kind !== "same").length;
  return (
    <div className="diff">
      <p className="muted small">
        From version <span className="mono">{shortId(documentId)}</span> to current. {changed} line
        {changed === 1 ? "" : "s"} differ.
      </p>
      <pre className="diff-body">
        {lines.map((l, i) => {
          // Keep two lines of context around each change; fold the rest.
          const near = lines.slice(Math.max(0, i - 2), i + 3).some((x) => x.kind !== "same");
          if (!near) {
            const prevShown =
              i === 0 || lines.slice(Math.max(0, i - 3), i + 2).some((x) => x.kind !== "same");
            return prevShown ? (
              <div key={i} className="dl dl-fold">
                ...
              </div>
            ) : null;
          }
          return (
            <div key={i} className={`dl dl-${l.kind}`}>
              <span className="dl-sign">{l.kind === "add" ? "+" : l.kind === "del" ? "-" : " "}</span>
              {l.text || " "}
            </div>
          );
        })}
      </pre>
    </div>
  );
}
