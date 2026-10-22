import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Note } from "../api";
import { ChangeRow, ErrorLine, Id, Loading, NoteLink, TypeBadge, fmtDate } from "../ui";

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint ? <div className="stat-hint">{hint}</div> : null}
    </div>
  );
}

function NoteList({ notes, empty, stale }: { notes: Note[]; empty: string; stale?: boolean }) {
  if (!notes.length) return <p className="muted">{empty}</p>;
  return (
    <ul className="list">
      {notes.map((n) => (
        <li key={n.note_id} className={stale ? "row-stale" : undefined}>
          <Id id={n.note_id} />
          <NoteLink note={n} />
          <span className="row-tail">
            <TypeBadge type={n.type} />
            {stale && n.review_by ? <span className="warn small mono">due {fmtDate(n.review_by)}</span> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function HomePage() {
  const q = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorLine error={q.error} />;
  const { status: s, open_loops, stale, recent_changes, projects } = q.data;
  const namespaces = Object.keys(s.ingestion_by_namespace ?? {}).length;
  return (
    <div className="stack">
      <section className="stats">
        <Stat label="active notes" value={s.notes.active} />
        <Stat label="archived" value={s.notes.archived} />
        <Stat label="projects" value={s.projects} />
        <Stat label="changes" value={s.changes} />
        <Stat label="sources" value={s.sources} />
        <Stat label="passages" value={s.passages} />
        <Stat
          label="ingestion"
          value={s.ingestion_complete ? "done" : "running"}
          hint={namespaces ? `${namespaces} namespaces` : undefined}
        />
      </section>

      <div className="cols">
        <section className="panel">
          <h2>
            Open loops <span className="count">{open_loops.length}</span>
          </h2>
          <NoteList notes={open_loops} empty="No open loops." />
        </section>
        <section className="panel panel-warn">
          <h2>
            Stale <span className="count">{stale.length}</span>
          </h2>
          <NoteList notes={stale} empty="Nothing past its review date." stale />
          {stale.length ? (
            <Link className="small" to="/memory?stale=1">
              All stale notes
            </Link>
          ) : null}
        </section>
      </div>

      <section className="panel">
        <h2>Recent changes</h2>
        {recent_changes.length ? (
          <ul className="changes">
            {recent_changes.slice(0, 20).map((c) => (
              <ChangeRow key={c.id} change={c} />
            ))}
          </ul>
        ) : (
          <p className="muted">No changes yet.</p>
        )}
        <Link className="small" to="/changes">
          Full log
        </Link>
      </section>

      <section className="panel">
        <h2>Projects</h2>
        <div className="chips">
          {projects.map((p) => (
            <Link
              key={p.key}
              className="chip"
              to={`/memory?scope=${encodeURIComponent(`project:${p.key}`)}`}
              title={p.title}
            >
              {p.key} <span className="muted">{p.active_notes}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
