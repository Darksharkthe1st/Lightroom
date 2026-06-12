import { useCallback, useEffect, useRef, useState } from "react";
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
  const running = analysis.pipeline_status === "running";
  const steps = [
    { label: "Triage", done: analysis.triage_complete, active: running && analysis.pipeline_phase === "scout" },
    { label: "Scout", done: analysis.scout_complete, active: running && analysis.pipeline_phase === "scout" },
    {
      label: "Deep dives",
      done: analysis.rabbit_holes_complete > 0,
      active: running && analysis.pipeline_phase === "rabbit_holes",
      detail: `${analysis.rabbit_holes_complete}/${analysis.rabbit_holes_planned}`,
    },
  ];
  return (
    <div>
      <div className="pipeline">
        {steps.map((s) => (
          <span
            key={s.label}
            className={`pipeline-step ${s.done ? "done" : ""} ${s.active ? "active" : ""}`}
          >
            {s.done ? "✓" : s.active ? "…" : "○"} {s.label}
            {s.detail ? ` (${s.detail})` : ""}
          </span>
        ))}
      </div>
      {analysis.pipeline_message && (
        <p className="pipeline-message muted">{analysis.pipeline_message}</p>
      )}
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
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => () => stopPolling(), []);

  const refreshRepo = useCallback(async (owner: string, name: string) => {
    const [summaryData, analysisData] = await Promise.all([
      apiClient.getRepoSummary(owner, name),
      apiClient.getRepoAnalysis(owner, name),
    ]);
    setSummary(summaryData);
    setAnalysis(analysisData);
    return analysisData;
  }, []);

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
    stopPolling();
    try {
      const [owner, name] = repo.full_name.split("/");
      const analysisData = await refreshRepo(owner, name);
      if (analysisData.pipeline_status === "running") {
        startPolling(owner, name);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load repository");
    }
  };

  const startPolling = (owner: string, name: string) => {
    stopPolling();
    setAnalyzing(true);
    pollRef.current = setInterval(async () => {
      try {
        const data = await refreshRepo(owner, name);
        if (data.pipeline_status === "failed") {
          stopPolling();
          setAnalyzing(false);
          setError(data.pipeline_message || "Analysis failed");
          return;
        }
        if (data.pipeline_status !== "running" && (data.bullets.length > 0 || data.scout_complete)) {
          stopPolling();
          setAnalyzing(false);
        }
      } catch (err) {
        stopPolling();
        setAnalyzing(false);
        setError(err instanceof Error ? err.message : "Failed to refresh analysis");
      }
    }, 3000);
  };

  const runAnalysis = async () => {
    if (!selectedRepo) return;
    const [owner, name] = selectedRepo.full_name.split("/");
    setAnalyzing(true);
    setError(null);
    try {
      const force = Boolean(analysis?.bullets.length);
      const result = await apiClient.runRepoAnalysis(owner, name, force);
      if (result.status === "running") {
        startPolling(owner, name);
        await refreshRepo(owner, name);
        return;
      }
      setResume(result);
      setView("resume");
      setAnalyzing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
      setAnalyzing(false);
    }
  };

  const logout = async () => {
    stopPolling();
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
          {analysis && analysis.bullets.length > 0 && (
            <div className="signals-section">
              <h3>Resume bullets</h3>
              <BulletList bullets={analysis.bullets} />
            </div>
          )}
          {analyzing && (
            <p className="muted analyzing-note">
              Cursor agents are working — scout and deep dives can take several minutes. This
              page updates automatically.
            </p>
          )}
          <button
            type="button"
            className="btn primary"
            onClick={runAnalysis}
            disabled={analyzing}
          >
            {analyzing
              ? "Analyzing…"
              : analysis && analysis.bullets.length > 0
                ? "Re-run analysis"
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
