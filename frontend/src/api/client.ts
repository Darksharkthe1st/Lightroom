const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

export interface GitHubUser {
  id: number;
  login: string;
  name: string | null;
  avatar_url: string | null;
}

export interface AuthStatus {
  authenticated: boolean;
  user: GitHubUser | null;
}

export interface Repository {
  id: number;
  name: string;
  full_name: string;
  description: string | null;
  html_url: string;
  private: boolean;
  language: string | null;
  updated_at: string | null;
  default_branch: string;
}

export interface RepositorySummary {
  full_name: string;
  title: string;
  summary: string;
  highlights: string[];
  tech_stack: string[];
  status: string;
}

export interface ResumeBullet {
  text: string;
  source_repo: string;
  evidence: string[];
  signal_id?: string | null;
}

export interface SignalNote {
  signal_id: string;
  display_name: string;
  summary: string;
}

export interface RepoAnalysis {
  full_name: string;
  status: string;
  triage_complete: boolean;
  scout_complete: boolean;
  rabbit_holes_planned: number;
  rabbit_holes_complete: number;
  findings_excerpt: string;
  signals: SignalNote[];
  bullets: ResumeBullet[];
  pipeline_status?: string | null;
  pipeline_phase?: string | null;
  pipeline_message?: string | null;
}

export interface ResumeResponse {
  username: string;
  bullets: ResumeBullet[];
  status: "pending" | "running" | "completed" | "failed";
  message: string | null;
}

export const apiClient = {
  authStatus: () => api<AuthStatus>("/api/auth/status"),
  logout: () => api<{ status: string }>("/api/auth/logout", { method: "POST" }),
  listRepos: () => api<Repository[]>("/api/repos"),
  getRepoSummary: (owner: string, repo: string) =>
    api<RepositorySummary>(`/api/repos/${owner}/${repo}`),
  getRepoAnalysis: (owner: string, repo: string) =>
    api<RepoAnalysis>(`/api/analysis/repo/${owner}/${repo}`),
  getResume: () => api<ResumeResponse>("/api/analysis/resume"),
  runResumeAnalysis: () =>
    api<ResumeResponse>("/api/analysis/resume", { method: "POST" }),
  runRepoAnalysis: (owner: string, repo: string, force = false) =>
    api<ResumeResponse>(
      `/api/analysis/resume/${owner}/${repo}${force ? "?force=true" : ""}`,
      { method: "POST" },
    ),
};

export function githubLoginUrl(): string {
  return `${API_BASE}/api/auth/github/login`;
}
