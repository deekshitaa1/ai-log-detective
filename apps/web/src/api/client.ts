const API_BASE =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(
    `${API_BASE}${path}`,
    {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    },
  );

  const text = await response.text();

  let data: unknown = null;

  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    let message = `HTTP ${response.status}`;

    if (
      data &&
      typeof data === "object" &&
      "detail" in data
    ) {
      message = String(
        (data as { detail: unknown }).detail,
      );
    } else if (typeof data === "string") {
      message = data;
    }

    throw new Error(message);
  }

  return data as T;
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
}

export interface Incident {
  id: string;
  project_id: string;
  title: string;
  description?: string | null;
  status: string;
  severity: string;
  started_at?: string | null;
  resolved_at?: string | null;
  created_at?: string | null;
}

export interface RepairCandidate {
  id: string;
  file_id?: string | null;
  file_path?: string | null;
  repair_type?: string | null;
  risk_level?: string | null;
  status?: string | null;
  github_pr_number?: number | null;
  github_pr_branch?: string | null;
  github_commit_sha?: string | null;
  github_pr_url?: string | null;
  merged_at?: string | null;
}

async function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

async function post<T>(
  path: string,
  body?: unknown,
): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body:
      body === undefined
        ? undefined
        : JSON.stringify(body),
  });
}

export const api = {
  projects: {
    list: () =>
      get<Project[]>(
        "/api/v1/projects",
      ),
  },

  incidents: {
    list: () =>
      get<Incident[]>(
        "/api/v1/incidents",
      ),

    get: (incidentId: string) =>
      get<Incident>(
        `/api/v1/incidents/${incidentId}`,
      ),

    detect: (incidentId: string) =>
      post(
        `/api/v1/incidents/${incidentId}/detect`,
      ),

    correlate: (incidentId: string) =>
      post(
        `/api/v1/incidents/${incidentId}/correlate`,
      ),

    rca: (incidentId: string) =>
      post(
        `/api/v1/incidents/${incidentId}/rca`,
      ),

    localize: (incidentId: string) =>
      post(
        `/api/v1/incidents/${incidentId}/localize`,
      ),

    repair: (incidentId: string) =>
      post(
        `/api/v1/incidents/${incidentId}/repair`,
      ),

    validateRepair: (
      incidentId: string,
      repairId: string,
    ) =>
      post(
        `/api/v1/incidents/${incidentId}/repair/${repairId}/validate`,
      ),

    verifyRepair: (
      incidentId: string,
      repairId: string,
    ) =>
      post(
        `/api/v1/incidents/${incidentId}/repair/${repairId}/verify`,
      ),

    createPullRequest: (
      incidentId: string,
      repairId: string,
    ) =>
      post(
        `/api/v1/incidents/${incidentId}/repair/${repairId}/pr`,
      ),

    syncRepair: (
      incidentId: string,
      repairId: string,
    ) =>
      post(
        `/api/v1/incidents/${incidentId}/repair/${repairId}/sync`,
      ),
  },

  health: () =>
    get<{
      status: string;
      service: string;
    }>("/health"),
};
