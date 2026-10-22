import { NavLink, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { Starfield } from "./Starfield";
import { HomePage } from "./pages/Home";
import { MemoryPage } from "./pages/Memory";
import { NotePage } from "./pages/Note";
import { NewNotePage } from "./pages/NewNote";
import { ChangesPage } from "./pages/Changes";
import { ProjectsPage } from "./pages/Projects";
import { BootPage } from "./pages/Boot";
import { SearchPage } from "./pages/Search";
import { PeoplePage } from "./pages/People";

const NAV = [
  ["/", "Home"],
  ["/memory", "Memory"],
  ["/people", "People"],
  ["/changes", "Changes"],
  ["/projects", "Projects"],
  ["/boot", "Boot"],
  ["/search", "Search"],
] as const;

export function App() {
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: Infinity });
  return (
    <>
      <Starfield />
      <header className="top">
        <div className="top-inner">
          <span className="brand">
            <span className="brand-mark" aria-hidden="true" />
            memory
          </span>
          <nav className="nav">
            {NAV.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"}>
                {label}
              </NavLink>
            ))}
          </nav>
          <span className="who mono" title="Signed in">
            {me.data?.email ?? (me.isError ? "not signed in" : "")}
          </span>
        </div>
      </header>
      <main className="page">
        {me.isError ? (
          <p className="error">Could not load your session: {(me.error as Error).message}</p>
        ) : null}
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/memory" element={<MemoryPage />} />
          <Route path="/memory/new" element={<NewNotePage />} />
          <Route path="/memory/:id" element={<NotePage />} />
          <Route path="/people" element={<PeoplePage />} />
          <Route path="/changes" element={<ChangesPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/boot" element={<BootPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="*" element={<p className="muted">Nothing here.</p>} />
        </Routes>
      </main>
    </>
  );
}
