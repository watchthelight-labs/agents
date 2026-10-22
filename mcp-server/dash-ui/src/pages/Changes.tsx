import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { ChangeRow, ErrorLine, Loading } from "../ui";

export function ChangesPage() {
  const [sp, setSp] = useSearchParams();
  const since = sp.get("since") ?? "";
  const noteId = sp.get("note") ?? "";
  const limit = Number(sp.get("limit") ?? 200) || 200;

  function set(k: string, v: string) {
    setSp(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (v) next.set(k, v);
        else next.delete(k);
        return next;
      },
      { replace: true },
    );
  }

  const q = useQuery({
    queryKey: ["changes", { since, noteId, limit }],
    queryFn: () => api.changes({ since, note_id: noteId, limit }),
    placeholderData: keepPreviousData,
  });

  return (
    <div className="stack">
      <h1>Changes</h1>
      <div className="filters">
        <label className="inline">
          since
          <input type="date" value={since} onChange={(e) => set("since", e.target.value)} />
        </label>
        <input
          className="mono"
          placeholder="note id"
          value={noteId}
          onChange={(e) => set("note", e.target.value.trim())}
          aria-label="Note id"
        />
        {since || noteId ? (
          <button className="btn btn-sm" onClick={() => setSp(new URLSearchParams(), { replace: true })}>
            Clear
          </button>
        ) : null}
      </div>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorLine error={q.error} />
      ) : q.data.changes.length ? (
        <>
          <ul className="changes panel">
            {q.data.changes.map((c) => (
              <ChangeRow key={c.id} change={c} />
            ))}
          </ul>
          {q.data.changes.length >= limit ? (
            <button className="btn" onClick={() => set("limit", String(limit + 200))}>
              Load more
            </button>
          ) : null}
        </>
      ) : (
        <p className="muted">No changes match.</p>
      )}
    </div>
  );
}
