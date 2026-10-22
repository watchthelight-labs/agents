import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { api, Receipt, ThreadBrief } from "../api";
import { ErrorLine, Loading, fmtDate, fmtTime, useInvalidate, useToast } from "../ui";

// Third-party text (titles, excerpts) is rendered as plain text only, never as markdown or HTML.

const STATES = ["active", "waiting_on_us", "waiting_on_them", "unlogged", "open", "closed", "dropped", "all"];

function useAct() {
  const toast = useToast();
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (fn: () => Promise<Receipt>) => fn(),
    onSuccess: (r: Receipt) => {
      toast(r.receipt);
      invalidate();
    },
    onError: (e) => toast((e as Error).message, "err"),
  });
}

function ThreadLine({ t, onOpen }: { t: ThreadBrief; onOpen: (id: number) => void }) {
  return (
    <li className="change">
      <div className="change-main">
        <span className="badge">{t.state.replace(/_/g, " ")}</span>
        <button className="linklike" onClick={() => onOpen(t.thread_id)}>
          {t.repo ? `${t.repo}#${t.number}` : t.title}
        </button>
        {t.repo ? <span className="muted small">{t.title}</span> : null}
      </div>
      <div className="change-meta">
        {t.unread ? <span className="warn small">{t.unread} unread</span> : null}
        {t.people.length ? <span className="small">{t.people.join(", ")}</span> : null}
        {t.why ? <span className="muted small">why: {t.why}</span> : null}
        <span className="mono small">{fmtDate(t.last_in_at ?? t.last_out_at)}</span>
        {t.url ? (
          <a className="small" href={t.url} target="_blank" rel="noreferrer noopener">
            open
          </a>
        ) : null}
      </div>
    </li>
  );
}

function ThreadView({ id, onClose }: { id: number; onClose: () => void }) {
  const q = useQuery({ queryKey: ["thread", id], queryFn: () => api.thread(id) });
  const act = useAct();
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorLine error={q.error} />;
  const { thread, interactions, people, follow, notes } = q.data;
  return (
    <div className="panel stack">
      <div className="filters">
        <h2>{thread.repo ? `${thread.repo}#${thread.number}` : thread.title}</h2>
        <button className="btn btn-sm" onClick={onClose}>
          Close
        </button>
      </div>
      {thread.repo ? <p className="muted">{thread.title}</p> : null}
      <p>
        <b>why:</b> {thread.why || "(not logged)"}
        {thread.stance ? (
          <>
            {" "}
            <b>stance:</b> {thread.stance}
          </>
        ) : null}
      </p>
      <p className="small">
        state {thread.state} · remote {thread.remote_state ?? "unknown"} · {thread.platform}
        {thread.project ? ` · ${thread.project}` : ""}
        {thread.tracker_ids.length ? ` · ${thread.tracker_ids.join(", ")}` : ""}
        {follow ? ` · checked ${fmtTime(follow.last_checked)}, next ${fmtTime(follow.next_check)}` : " · not followed"}
        {follow?.last_error ? ` · ${follow.last_error}` : ""}
      </p>
      {people.length ? <p className="small">people: {people.map((p) => `${p.display} (${p.handles.join(", ")})`).join("; ")}</p> : null}
      {notes.length ? <p className="small">notes: {notes.map((n) => n.title).join("; ")}</p> : null}
      <div className="filters">
        {thread.unread ? (
          <button className="btn btn-sm" onClick={() => act.mutate(() => api.markSeen({ thread_id: id }))}>
            Mark seen
          </button>
        ) : null}
        <button className="btn btn-sm" onClick={() => act.mutate(() => api.markSeen({ thread_id: id, snooze_days: 7 }))}>
          Snooze 7 days
        </button>
        {["closed", "dropped"].includes(thread.state) ? null : (
          <button className="btn btn-sm" onClick={() => act.mutate(() => api.updateThread(id, { state: "closed" }))}>
            Close thread
          </button>
        )}
      </div>
      <ul className="changes">
        {interactions.map((i) => (
          <li key={i.id} className="change">
            <div className="change-main">
              <span className="badge">{i.direction === "out" ? "we said" : i.direction === "in" ? i.author ?? "they said" : "note"}</span>
              <span className="change-summary">{i.summary || i.excerpt || i.kind}</span>
            </div>
            <div className="change-meta">
              <time className="mono small">{fmtTime(i.ts)}</time>
              {i.direction === "in" && !i.seen_at ? <span className="warn small">unread</span> : null}
              {i.url ? (
                <a className="small" href={i.url} target="_blank" rel="noreferrer noopener">
                  link
                </a>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      <p className="muted small">{q.data.guidance}</p>
    </div>
  );
}

export function PeoplePage() {
  const [sp, setSp] = useSearchParams();
  const state = sp.get("state") ?? "active";
  const text = sp.get("q") ?? "";
  const open = Number(sp.get("thread") ?? 0) || 0;
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
  const inbox = useQuery({ queryKey: ["inbox"], queryFn: api.inbox });
  const threads = useQuery({
    queryKey: ["threads", { state, text }],
    queryFn: () => api.threads({ state, q: text }),
    placeholderData: keepPreviousData,
  });
  const act = useAct();
  const onOpen = (id: number) => set("thread", String(id));
  const p = inbox.data?.poller;
  return (
    <div className="stack">
      <h1>People</h1>
      {open ? <ThreadView id={open} onClose={() => set("thread", "")} /> : null}
      <section className="stack">
        <h2>Inbox</h2>
        {inbox.isPending ? (
          <Loading />
        ) : inbox.isError ? (
          <ErrorLine error={inbox.error} />
        ) : (
          <>
            <p className="small muted">
              poller: last run {fmtTime(p?.last_run)} · last ok {fmtTime(p?.last_ok)} · {p?.follows} follows
              {p?.failing_follows ? ` · ${p.failing_follows} failing` : ""}
              {p?.rate_remaining != null ? ` · rate ${p.rate_remaining}` : ""}
              {p?.last_errors.length ? ` · ${p.last_errors[0]}` : ""}
            </p>
            {inbox.data.unread.length ? (
              <ul className="changes panel">
                {inbox.data.unread.map((u) => (
                  <li key={u.event_id} className="change">
                    <div className="change-main">
                      <span className="badge">{u.author ?? "someone"}</span>
                      <button className="linklike" onClick={() => onOpen(u.thread_id)}>
                        {u.title}
                      </button>
                    </div>
                    <div className="change-meta">
                      <span className="small">{u.excerpt}</span>
                      <time className="mono small">{fmtTime(u.ts)}</time>
                      <button className="btn btn-sm" onClick={() => act.mutate(() => api.markSeen({ event_ids: [u.event_id] }))}>
                        Seen
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No unread replies.</p>
            )}
            {inbox.data.due.length ? (
              <>
                <h3>Follow-ups due</h3>
                <ul className="changes panel">
                  {inbox.data.due.map((t) => (
                    <ThreadLine key={t.thread_id} t={t} onOpen={onOpen} />
                  ))}
                </ul>
              </>
            ) : null}
            {inbox.data.unlogged.length ? (
              <>
                <h3>Threads we are in but never logged</h3>
                <ul className="changes panel">
                  {inbox.data.unlogged.map((t) => (
                    <ThreadLine key={t.thread_id} t={t} onOpen={onOpen} />
                  ))}
                </ul>
              </>
            ) : null}
          </>
        )}
      </section>
      <section className="stack">
        <h2>Threads</h2>
        <div className="filters">
          <select value={state} onChange={(e) => set("state", e.target.value)} aria-label="State">
            {STATES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <input placeholder="search title, why, repo" value={text} onChange={(e) => set("q", e.target.value)} aria-label="Search" />
        </div>
        {threads.isPending ? (
          <Loading />
        ) : threads.isError ? (
          <ErrorLine error={threads.error} />
        ) : threads.data.threads.length ? (
          <ul className="changes panel">
            {threads.data.threads.map((t) => (
              <ThreadLine key={t.thread_id} t={t} onOpen={onOpen} />
            ))}
          </ul>
        ) : (
          <p className="muted">No threads match.</p>
        )}
      </section>
    </div>
  );
}
