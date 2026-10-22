import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, errMsg, type Project } from "../api";
import { ErrorLine, Loading, useInvalidate, useToast } from "../ui";

const lines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

export function ProjectsPage() {
  const q = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const [editing, setEditing] = useState<string | null>(null);
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorLine error={q.error} />;
  const projects = [...q.data.projects].sort((a, b) => a.key.localeCompare(b.key));
  return (
    <div className="stack">
      <h1>Projects</h1>
      <ul className="projects">
        {projects.map((p) => (
          <li key={p.key} className="panel project">
            <div className="project-head">
              <button className="btn-link project-key mono" onClick={() => setEditing(editing === p.key ? null : p.key)}>
                {p.key}
              </button>
              <span className="project-title">{p.title}</span>
              <Link className="small" to={`/memory?scope=${encodeURIComponent(`project:${p.key}`)}`}>
                {p.active_notes} note{p.active_notes === 1 ? "" : "s"}
              </Link>
            </div>
            {p.summary ? <p className="muted small">{p.summary}</p> : null}
            <div className="kv small">
              {p.aliases.length ? (
                <span>
                  <b>aliases</b> <span className="mono">{p.aliases.join(", ")}</span>
                </span>
              ) : null}
              {p.path_globs.length ? (
                <span>
                  <b>paths</b> <span className="mono">{p.path_globs.join(", ")}</span>
                </span>
              ) : null}
              {p.git_remotes.length ? (
                <span>
                  <b>remotes</b> <span className="mono">{p.git_remotes.join(", ")}</span>
                </span>
              ) : null}
            </div>
            {editing === p.key ? <ProjectForm project={p} onClose={() => setEditing(null)} /> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProjectForm({ project, onClose }: { project: Project; onClose: () => void }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const [title, setTitle] = useState(project.title);
  const [summary, setSummary] = useState(project.summary);
  const [globs, setGlobs] = useState(project.path_globs.join("\n"));
  const [remotes, setRemotes] = useState(project.git_remotes.join("\n"));
  const [aliases, setAliases] = useState(project.aliases.join("\n"));
  const m = useMutation({
    mutationFn: () =>
      api.updateProject(project.key, {
        title,
        summary,
        path_globs: lines(globs),
        git_remotes: lines(remotes),
        aliases: lines(aliases),
      }),
    onSuccess: (p) => {
      const receipt = (p as Project & { receipt?: string }).receipt;
      toast(receipt || `Saved project ${p.key}.`);
      invalidate();
      onClose();
    },
    onError: (e) => toast(errMsg(e), "err"),
  });
  return (
    <form
      className="form"
      onSubmit={(e) => {
        e.preventDefault();
        m.mutate();
      }}
    >
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Summary
        <textarea rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} />
      </label>
      <div className="grid-form grid-3">
        <label>
          Path globs, one per line
          <textarea className="mono" rows={4} value={globs} onChange={(e) => setGlobs(e.target.value)} />
        </label>
        <label>
          Git remotes, one per line
          <textarea className="mono" rows={4} value={remotes} onChange={(e) => setRemotes(e.target.value)} />
        </label>
        <label>
          Aliases, one per line
          <textarea className="mono" rows={4} value={aliases} onChange={(e) => setAliases(e.target.value)} />
        </label>
      </div>
      <div className="actions">
        <button className="btn btn-primary" disabled={m.isPending}>
          Save
        </button>
        <button type="button" className="btn" onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  );
}
