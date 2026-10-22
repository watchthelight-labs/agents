import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, NOTE_TYPES } from "../api";
import { ErrorLine, Id, Loading, StaleBadge, TypeBadge, fmtDate } from "../ui";

const PAGE = 100;

export function MemoryPage() {
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const type = sp.get("type") ?? "";
  const scope = sp.get("scope") ?? "";
  const status: "active" | "archived" = sp.get("status") === "archived" ? "archived" : "active";
  const stale = sp.get("stale") === "1";
  const q = sp.get("q") ?? "";
  const offset = Number(sp.get("offset") ?? 0) || 0;
  const [qDraft, setQDraft] = useState(q);
  useEffect(() => setQDraft(q), [q]);

  function set(k: string, v: string) {
    setSp(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (v) next.set(k, v);
        else next.delete(k);
        if (k !== "offset") next.delete("offset");
        return next;
      },
      { replace: true },
    );
  }

  // Debounce the title search into the URL.
  useEffect(() => {
    if (qDraft.trim() === q) return;
    const t = window.setTimeout(() => set("q", qDraft.trim()), 300);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qDraft]);

  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const notes = useQuery({
    queryKey: ["notes", { type, scope, status, stale, q, offset }],
    queryFn: () => api.notes({ type, scope, status, stale, q, limit: PAGE, offset }),
    placeholderData: keepPreviousData,
  });

  const rows = notes.data ? [...notes.data.notes].sort((a, b) => Number(b.pinned) - Number(a.pinned)) : [];

  return (
    <div className="stack">
      <div className="bar">
        <h1>Memory</h1>
        <Link className="btn btn-primary" to="/memory/new">
          New note
        </Link>
      </div>
      <div className="filters">
        <input
          type="search"
          placeholder="Title"
          value={qDraft}
          onChange={(e) => setQDraft(e.target.value)}
          aria-label="Title search"
        />
        <select value={type} onChange={(e) => set("type", e.target.value)} aria-label="Type">
          <option value="">any type</option>
          {NOTE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select value={scope} onChange={(e) => set("scope", e.target.value)} aria-label="Scope">
          <option value="">any scope</option>
          <option value="global">global</option>
          {projects.data?.projects.map((p) => (
            <option key={p.key} value={`project:${p.key}`}>
              project:{p.key}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => set("status", e.target.value === "active" ? "" : e.target.value)}
          aria-label="Status"
        >
          <option value="active">active</option>
          <option value="archived">archived</option>
        </select>
        <label className="check">
          <input type="checkbox" checked={stale} onChange={(e) => set("stale", e.target.checked ? "1" : "")} />
          stale only
        </label>
      </div>

      {notes.isPending ? (
        <Loading />
      ) : notes.isError ? (
        <ErrorLine error={notes.error} />
      ) : (
        <>
          <p className="muted small">
            {notes.data.total} note{notes.data.total === 1 ? "" : "s"}
            {notes.isFetching ? ", refreshing" : ""}
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>id</th>
                  <th>title</th>
                  <th>type</th>
                  <th className="hide-sm">scope</th>
                  <th className="hide-sm">updated</th>
                  <th className="hide-sm">review</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((n) => (
                  <tr
                    key={n.note_id}
                    className={`clickable${n.stale ? " row-stale" : ""}`}
                    onClick={() => nav(`/memory/${n.note_id}`)}
                  >
                    <td>
                      <Id id={n.note_id} />
                    </td>
                    <td className="cell-title">
                      <Link to={`/memory/${n.note_id}`} onClick={(e) => e.stopPropagation()}>
                        {n.title || "(untitled)"}
                      </Link>
                      {n.pinned ? <span className="badge badge-pin">pinned</span> : null}
                      {n.stale ? <StaleBadge /> : null}
                      {n.status === "archived" ? <span className="badge">archived</span> : null}
                    </td>
                    <td>
                      <TypeBadge type={n.type} />
                    </td>
                    <td className="hide-sm mono small">{n.scope}</td>
                    <td className="hide-sm mono small">{fmtDate(n.updated_at)}</td>
                    <td className={`hide-sm mono small${n.stale ? " warn" : ""}`}>{fmtDate(n.review_by)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {notes.data.total > PAGE ? (
            <div className="pager">
              <button
                className="btn btn-sm"
                disabled={offset === 0}
                onClick={() => set("offset", String(Math.max(0, offset - PAGE)))}
              >
                Previous
              </button>
              <span className="muted small mono">
                {offset + 1} to {Math.min(offset + PAGE, notes.data.total)} of {notes.data.total}
              </span>
              <button
                className="btn btn-sm"
                disabled={offset + PAGE >= notes.data.total}
                onClick={() => set("offset", String(offset + PAGE))}
              >
                Next
              </button>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
