import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { ErrorLine, Loading, Markdown } from "../ui";

const LIMIT = 9200;
const PARTS = ["profile", "project", "threads"] as const;

export function BootPage() {
  const projects = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const [cwd, setCwd] = useState("");
  const [project, setProject] = useState("");
  const [args, setArgs] = useState<{ cwd?: string; project?: string } | null>(null);
  const q = useQuery({
    queryKey: ["boot", args],
    queryFn: () => api.boot(args ?? {}),
    enabled: args !== null,
  });

  return (
    <div className="stack">
      <h1>Boot</h1>
      <p className="muted small">What a new session gets at start, for a folder or a project.</p>
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          setArgs({ cwd: cwd.trim() || undefined, project: project || undefined });
        }}
      >
        <input
          className="mono grow"
          placeholder="Folder path, like ~\projects\site"
          value={cwd}
          onChange={(e) => setCwd(e.target.value)}
          aria-label="Folder path"
        />
        <select value={project} onChange={(e) => setProject(e.target.value)} aria-label="Project">
          <option value="">no project</option>
          {projects.data?.projects.map((p) => (
            <option key={p.key} value={p.key}>
              {p.key}
            </option>
          ))}
        </select>
        <button className="btn btn-primary">Load</button>
      </form>

      {args === null ? null : q.isPending ? (
        <Loading what="boot context" />
      ) : q.isError ? (
        <ErrorLine error={q.error} />
      ) : (
        <>
          <p className="small">
            Matched project:{" "}
            {q.data.project ? (
              <Link className="mono" to={`/memory?scope=${encodeURIComponent(`project:${q.data.project.key}`)}`}>
                {q.data.project.key}
              </Link>
            ) : (
              <span className="muted">none</span>
            )}
          </p>
          {PARTS.map((k) => {
            const text = q.data.parts[k] ?? "";
            const over = text.length > LIMIT;
            const pct = Math.min(100, (text.length / LIMIT) * 100);
            return (
              <details key={k} className="panel boot-part" open={k !== "profile"}>
                <summary>
                  <span className="boot-name">{k}</span>
                  <span className={`mono small${over ? " danger" : " muted"}`}>
                    {text.length.toLocaleString()} / {LIMIT.toLocaleString()}
                  </span>
                  <span className="meter" aria-hidden="true">
                    <span className={`meter-fill${over ? " over" : ""}`} style={{ width: `${pct}%` }} />
                  </span>
                </summary>
                {text ? <Markdown text={text} /> : <p className="muted">Empty.</p>}
              </details>
            );
          })}
          <p className="muted small">Infra context is added by the client, not this API.</p>
        </>
      )}
    </div>
  );
}
