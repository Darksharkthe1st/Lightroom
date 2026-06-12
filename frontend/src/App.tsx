import { useCallback, useEffect, useState } from "react";
import {
  apiClient,
  githubLoginUrl,
  type GitHubUser,
  type RepoAnalysis,
  type Repository,
  type RepositorySummary,
  type ResumeResponse,
} from "./api/client";
import "./App.css";

type View = "repos" | "repo-detail" | "resume";

function PipelineBar({ analysis }: { analysis: RepoAnalysis | null }) {
  if (!analysis) return null;
  const steps = [
    { label: "Triage", done: analysis.triage_complete },
    { label: "Scout", done: analysis.scout_complete },
    {
      label: "Deep dives",
      done: analysis.rabbit_holes_complete > 0,
      detail: `${analysis.rabbit_holes_complete}/${analysis.rabbit_holes_planned}`,
    },
  ];
  return (
    <div className="pipeline">
      {steps.map((s) => (
        <span key={s.label} className={`pipeline-step ${s.done ? "done" : ""}`}>
          {s.done ? "✓" : "○"} {s.label}
          {s.detail ? ` (${s.detail})` : ""}
        </span>
      ))}
    </div>
  );
}

function BulletList({ bullets }: { bullets: ResumeResponse["bullets"] }) {
  if (bullets.length === 0) {
    return <p className="muted">No bullets yet. Run analysis to generate.</p>;
  }
  return (
    <ul className="bullet-list">
      {bullets.map((bullet, i) => (
        <li key={`${bullet.source_repo}-${bullet.signal_id ?? i}`} className="bullet-card">
          <p>{bullet.text}</p>
          <span className="meta">
            {bullet.signal_id ? `signal: ${bullet.signal_id}` : bullet.source_repo}
          </span>
          {bullet.evidence.length > 0 && (
            <details>
              <summary>Evidence</summary>
              <ul>
                {bullet.evidence.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            </details>
          )}
        </li>
      ))}
    </ul>
  );
}

function App() {
  const [user, setUser] = useState<GitHubUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [summary, setSummary] = useState<RepositorySummary | null>(null);
  const [analysis, setAnalysis] = useState<RepoAnalysis | null>(null);
  const [resume, setResume] = useState<ResumeResponse | null>(null);
  const [view, setView] = useState<View>("repos");
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const checkAuth = useCallback(async () => {
    try {
      const status = await apiClient.authStatus();
      setUser(status.authenticated ? status.user : null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const authError = params.get("auth_error");
    if (authError) {
      setError(`GitHub auth failed: ${authError}`);
      window.history.replaceState({}, "", window.location.pathname);
    }
    if (params.get("auth") === "success") {
      window.history.replaceState({}, "", window.location.pathname);
    }
    checkAuth();
  }, [checkAuth]);

  const loadRepos = async () => {
    setError(null);
    try {
      const data = await apiClient.listRepos();
      setRepos(data);
      setView("repos");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load repositories");
    }
  };

  const openRepo = async (repo: Repository) => {
    setError(null);
    setSelectedRepo(repo);
    setView("repo-detail");
    setAnalysis(null);
    setSummary(null);
    try {
      const [owner, name] = repo.full_name.split("/");
      const [summaryData, analysisData] = await Promise.all([
        apiClient.getRepoSummary(owner, name),
        apiClient.getRepoAnalysis(owner, name),
      ]);
      setSummary(summaryData);
      setAnalysis(analysisData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load repository");
    }
  };

  const runAnalysis = async (scope: "all" | "single") => {
    setAnalyzing(true);
    setError(null);
    try {
      let result: ResumeResponse;
      if (scope === "single" && selectedRepo) {
        const [owner, name] = selectedRepo.full_name.split("/");
        result = await apiClient.runRepoAnalysis(owner, name);
      } else {
        result = await apiClient.runResumeAnalysis();
      }
      setResume(result);
      setView("resume");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const logout = async () => {
    await apiClient.logout();
    setUser(null);
    setRepos([]);
    setSelectedRepo(null);
    setSummary(null);
    setAnalysis(null);
    setResume(null);
    setView("repos");
  };

  if (loading) {
    return (
      <div className="app">
        <p className="muted">Loading...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="app landing">
        <header>
          <h1>Lightroom</h1>
          <p>
            Cursor agents analyze your GitHub repos and turn real contributions into
            recruiter-ready resume bullets.
          </p>
        </header>
        {error && <p className="error">{error}</p>}
        <a className="btn primary" href={githubLoginUrl()}>
          Authorize with GitHub
        </a>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>Lightroom</h1>
          <p className="muted">
            Signed in as <strong>{user.login}</strong>
          </p>
        </div>
        <div className="topbar-actions">
          <button type="button" className="btn" onClick={loadRepos}>
            Repositories
          </button>
          <button type="button" className="btn ghost" onClick={logout}>
            Log out
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      {view === "repos" && (
        <section>
          {repos.length === 0 ? (
            <button type="button" className="btn primary" onClick={loadRepos}>
              Load my repositories
            </button>
          ) : (
            <ul className="repo-list">
              {repos.map((repo) => (
                <li key={repo.id}>
                  <button type="button" className="repo-card" onClick={() => openRepo(repo)}>
                    <strong>{repo.full_name}</strong>
                    {repo.description && <span>{repo.description}</span>}
                    <span className="meta">
                      {repo.language || "—"} · {repo.private ? "private" : "public"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {view === "repo-detail" && selectedRepo && (
        <section className="detail">
          <button type="button" className="btn ghost back" onClick={() => setView("repos")}>
            ← Back
          </button>
          <h2>{selectedRepo.full_name}</h2>
          <PipelineBar analysis={analysis} />
          {summary ? (
            <article className="summary-card">
              <p className="badge">{summary.status}</p>
              <h3>{summary.title}</h3>
              <p>{summary.summary}</p>
              {summary.tech_stack.length > 0 && (
                <p className="tech">Stack: {summary.tech_stack.join(" · ")}</p>
              )}
            </article>
          ) : (
            <p className="muted">Loading summary...</p>
          )}
          {analysis && analysis.signals.length > 0 && (
            <div className="signals-section">
              <h3>Deep dives</h3>
              <ul className="signal-list">
                {analysis.signals.map((s) => (
                  <li key={s.signal_id} className="signal-card">
                    <strong>{s.display_name}</strong>
                    <p>{s.summary}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {analysis && analysis.bullets.length > 0 ? (
            <div className="signals-section">
              <h3>Resume bullets</h3>
              <BulletList bullets={analysis.bullets} />
            </div>
          ) : analysis?.status === "pending" ? (
            <p className="muted demo-hint">
              No AI analysis for this repo yet. Try <strong>Darksharkthe1st/CodeRunner</strong>{" "}
              for the full demo, or run the scout CLI to analyze this repo.
            </p>
          ) : null}
          <button
            type="button"
            className="btn primary"
            onClick={() => runAnalysis("single")}
            disabled={analyzing}
          >
            {analyzing
              ? "Loading..."
              : analysis && analysis.bullets.length > 0
                ? "Open resume view"
                : "Generate resume bullets"}
          </button>
        </section>
      )}

      {view === "resume" && resume && (
        <section className="resume">
          <button type="button" className="btn ghost back" onClick={() => setView("repos")}>
            ← Back to repos
          </button>
          <h2>Resume bullets for {resume.username}</h2>
          <p className="muted">{resume.message}</p>
          <BulletList bullets={resume.bullets} />
        </section>
      )}
    </div>
  );
}

export default App;
