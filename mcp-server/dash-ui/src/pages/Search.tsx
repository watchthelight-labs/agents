import { useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, type SearchResult } from "../api";
import { ErrorLine, Loading, Markdown, TypeBadge, fmtDate } from "../ui";

// Excerpts mark hits as [term]. Turn those into <mark>.
function highlight(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\[([^\]\n]{1,80})\]/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(<mark key={i++}>{m[1]}</mark>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function noteIdFrom(source: string): string | null {
  const m = /^notes\/([0-9a-f]{32})$/.exec(source);
  return m ? m[1] : null;
}

export function SearchPage() {
  const [sp, setSp] = useSearchParams();
  const q = sp.get("q") ?? "";
  const mode = sp.get("mode") === "any" ? "any" : "all";
  const kind = sp.get("kind") ?? "";
  const archived = sp.get("archived") === "1";
  const [draft, setDraft] = useState(q);
  const [open, setOpen] = useState<SearchResult | null>(null);
  useEffect(() => setDraft(q), [q]);

  const overview = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const kinds = Object.keys(overview.data?.status.by_kind ?? {}).sort();

  const res = useQuery({
    queryKey: ["search", { q, mode, kind, archived }],
    queryFn: () => api.search({ q, mode, kind, archived }),
    enabled: q.length > 0,
    placeholderData: keepPreviousData,
  });

  function set(k: string, v: string) {
    setSp(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (v) next.set(k, v);
        else next.delete(k);
        return next;
      },
      { replace: k !== "q" },
    );
  }

  return (
    <div className="stack">
      <h1>Search</h1>
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          setOpen(null);
          set("q", draft.trim());
        }}
      >
        <input
          type="search"
          className="grow"
          placeholder="Words to find"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          aria-label="Query"
          autoFocus
        />
        <select value={mode} onChange={(e) => set("mode", e.target.value === "all" ? "" : e.target.value)} aria-label="Mode">
          <option value="all">all words</option>
          <option value="any">any word</option>
        </select>
        <select value={kind} onChange={(e) => set("kind", e.target.value)} aria-label="Kind">
          <option value="">any kind</option>
          {kinds.map((k) => (
            <option key={k}>{k}</option>
          ))}
        </select>
        <label className="check">
          <input type="checkbox" checked={archived} onChange={(e) => set("archived", e.target.checked ? "1" : "")} />
          include archived
        </label>
        <button className="btn btn-primary">Search</button>
      </form>

      {open ? <Reader result={open} onClose={() => setOpen(null)} /> : null}

      {!q ? null : res.isPending ? (
        <Loading />
      ) : res.isError ? (
        <ErrorLine error={res.error} />
      ) : res.data.results.length ? (
        <ul className="results">
          {res.data.results.map((r) => {
            const nid = noteIdFrom(r.source);
            const active = open?.document_id === r.document_id && open.ordinal === r.ordinal;
            return (
              <li key={`${r.document_id}:${r.ordinal}`} className={`panel result${active ? " active" : ""}`}>
                <div className="result-head">
                  <button className="btn-link result-title" onClick={() => setOpen(r)}>
                    {r.title || r.source}
                  </button>
                  <span className="row-tail">
                    {r.note_type ? <TypeBadge type={r.note_type} /> : <span className="badge">{r.kind}</span>}
                    {r.note_scope ? <span className="mono small muted">{r.note_scope}</span> : null}
                    {r.source_date ? <span className="mono small muted">{fmtDate(r.source_date)}</span> : null}
                  </span>
                </div>
                <p className="excerpt">{highlight(r.excerpt)}</p>
                <div className="small muted result-foot">
                  <span className="mono wrap">{r.source}</span>
                  <span className="mono">#{r.ordinal}</span>
                  {nid ? <Link to={`/memory/${nid}`}>open note</Link> : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="muted">No matches.</p>
      )}
    </div>
  );
}

function Reader({ result, onClose }: { result: SearchResult; onClose: () => void }) {
  const [start, setStart] = useState(result.ordinal);
  useEffect(() => setStart(result.ordinal), [result.document_id, result.ordinal]);
  const q = useQuery({
    queryKey: ["source", result.document_id, start],
    queryFn: () => api.source(result.document_id, start, 2),
    placeholderData: keepPreviousData,
  });
  return (
    <section className="panel reader">
      <div className="reader-head">
        <h2>{q.data?.current_sources[0]?.title || result.title || "Source"}</h2>
        <button className="btn btn-sm" onClick={onClose}>
          Close
        </button>
      </div>
      {q.isPending ? (
        <Loading what="passages" />
      ) : q.isError ? (
        <ErrorLine error={q.error} />
      ) : (
        <>
          <p className="small muted">
            <span className="mono wrap">{q.data.current_sources.map((s) => s.uri).join(", ")}</span>{" "}
            <span className="mono">
              {`chunk ${start + 1}`}
              {q.data.passages.length > 1 ? `-${start + q.data.passages.length}` : ""} of {q.data.total_chunks}
            </span>
          </p>
          {q.data.passages.map((p) => (
            <div key={p.ordinal} className="passage">
              <div className="mono small muted">
                #{p.ordinal} chars {p.start_char}-{p.end_char}
              </div>
              <Markdown text={p.text} />
            </div>
          ))}
          <div className="pager">
            <button className="btn btn-sm" disabled={start <= 0} onClick={() => setStart(Math.max(0, start - 2))}>
              Previous
            </button>
            <button
              className="btn btn-sm"
              disabled={q.data.next_chunk == null}
              onClick={() => q.data.next_chunk != null && setStart(q.data.next_chunk)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}
