import { useCallback, useEffect, useState } from "react";
import {
  apiClient,
  githubLoginUrl,
  type GitHubUser,
  type Repository,
  type RepositorySummary,
  type ResumeResponse,
} from "./api/client";
import "./App.css";

type View = "repos" | "repo-detail" | "resume";

function App() {
  const [user, setUser] = useState<GitHubUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [summary, setSummary] = useState<RepositorySummary | null>(null);
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
    try {
      const [owner, name] = repo.full_name.split("/");
      const data = await apiClient.getRepoSummary(owner, name);
      setSummary(data);
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
          <p>Connect GitHub to explore your repositories and generate resume bullets.</p>
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
          <button type="button" className="btn" onClick={() => runAnalysis("all")} disabled={analyzing}>
            {analyzing ? "Analyzing..." : "Analyze all repos"}
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
          {summary ? (
            <article className="summary-card">
              <p className="badge">{summary.status}</p>
              <h3>{summary.title}</h3>
              <p>{summary.summary}</p>
              {summary.highlights.length > 0 && (
                <ul>
                  {summary.highlights.map((h) => (
                    <li key={h}>{h}</li>
                  ))}
                </ul>
              )}
              {summary.tech_stack.length > 0 && (
                <p className="tech">
                  Stack: {summary.tech_stack.join(", ")}
                </p>
              )}
            </article>
          ) : (
            <p className="muted">Loading summary...</p>
          )}
          <button
            type="button"
            className="btn primary"
            onClick={() => runAnalysis("single")}
            disabled={analyzing}
          >
            {analyzing ? "Analyzing..." : "Generate resume bullets for this repo"}
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
          {resume.bullets.length === 0 ? (
            <p>No bullets yet. Run analysis on a repository first.</p>
          ) : (
            <ul className="bullet-list">
              {resume.bullets.map((bullet, i) => (
                <li key={`${bullet.source_repo}-${i}`} className="bullet-card">
                  <p>{bullet.text}</p>
                  <span className="meta">from {bullet.source_repo}</span>
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
          )}
        </section>
      )}
    </div>
  );
}

export default App;
