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
  getResume: () => api<ResumeResponse>("/api/analysis/resume"),
  runResumeAnalysis: () =>
    api<ResumeResponse>("/api/analysis/resume", { method: "POST" }),
  runRepoAnalysis: (owner: string, repo: string) =>
    api<ResumeResponse>(`/api/analysis/resume/${owner}/${repo}`, { method: "POST" }),
};

export function githubLoginUrl(): string {
  return `${API_BASE}/api/auth/github/login`;
}
