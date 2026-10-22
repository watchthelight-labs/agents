import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, errMsg, NOTE_TYPES, type DuplicateCandidate } from "../api";
import { Id, TypeBadge, useInvalidate, useToast } from "../ui";

export function NewNotePage() {
  const nav = useNavigate();
  const toast = useToast();
  const invalidate = useInvalidate();
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const [title, setTitle] = useState("");
  const [type, setType] = useState("fact");
  const [scope, setScope] = useState("global");
  const [content, setContent] = useState("");
  const [forceNew, setForceNew] = useState(false);
  const [dupes, setDupes] = useState<{ candidates: DuplicateCandidate[]; hint: string } | null>(null);

  const m = useMutation({
    mutationFn: () => api.createNote({ title, content, type, scope, force_new: forceNew || undefined }),
    onSuccess: (r) => {
      if (r.status === "saved") {
        toast(r.receipt);
        invalidate(r.note_id);
        nav(`/memory/${r.note_id}`);
      } else {
        setDupes({ candidates: r.candidates, hint: r.hint });
      }
    },
    onError: (e) => toast(errMsg(e), "err"),
  });

  return (
    <div className="stack">
      <div className="crumbs small">
        <Link to="/memory">Memory</Link> / new
      </div>
      <h1>New note</h1>
      <form
        className="panel form"
        onSubmit={(e) => {
          e.preventDefault();
          setDupes(null);
          m.mutate();
        }}
      >
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required autoFocus />
        </label>
        <div className="grid-form">
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
              <option value="global">global</option>
              {projects.data?.projects.map((p) => (
                <option key={p.key} value={`project:${p.key}`}>
                  project:{p.key}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Content (markdown)
          <textarea rows={14} value={content} onChange={(e) => setContent(e.target.value)} required />
        </label>
        <label className="check">
          <input type="checkbox" checked={forceNew} onChange={(e) => setForceNew(e.target.checked)} />
          save as new even if it looks like a duplicate
        </label>
        <div className="actions">
          <button className="btn btn-primary" disabled={m.isPending}>
            {m.isPending ? "Saving" : "Save"}
          </button>
        </div>
      </form>

      {dupes ? (
        <section className="panel panel-warn">
          <h2>Possible duplicates</h2>
          <p className="muted">Not saved. These look close to what you wrote.</p>
          <ul className="list">
            {dupes.candidates.map((c) => (
              <li key={c.note_id} className="dupe">
                <Id id={c.note_id} />
                <Link to={`/memory/${c.note_id}`}>{c.title}</Link>
                <span className="row-tail">
                  <TypeBadge type={c.type} />
                  <span className="mono small muted">{c.score.toFixed(2)}</span>
                </span>
                {c.excerpt ? <p className="excerpt">{c.excerpt}</p> : null}
              </li>
            ))}
          </ul>
          <p className="small muted">Edit one of these instead, or tick the box above and save again.</p>
        </section>
      ) : null}
    </div>
  );
}
