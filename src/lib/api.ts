import type {
  AuthResponse,
  LineupResult,
  Player,
  SalaryStatus,
  Settings,
} from "./types"

async function request<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(url, {
    credentials: "include",
    ...options,
  })
  if (res.status === 401) {
    throw new AuthError()
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

export class AuthError extends Error {
  constructor() {
    super("Not authenticated")
    this.name = "AuthError"
  }
}

export async function login(password: string): Promise<AuthResponse> {
  return request("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  })
}

export async function logout(): Promise<void> {
  await request("/api/logout", { method: "POST" })
}

export async function checkAuth(): Promise<AuthResponse> {
  return request("/api/auth/check")
}

export async function optimize(params: {
  start_date?: string
  locked_players?: string[]
  excluded_players?: string[]
}): Promise<LineupResult> {
  return request("/api/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  })
}

export async function getSettings(): Promise<Settings> {
  return request("/api/settings")
}

export async function updateSettings(
  settings: Partial<Settings>
): Promise<Settings> {
  return request("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  })
}

export async function uploadSalary(file: File): Promise<{ count: number }> {
  const formData = new FormData()
  formData.append("file", file)
  return request("/api/salary/upload", {
    method: "POST",
    body: formData,
  })
}

export async function getSalaryStatus(): Promise<SalaryStatus> {
  return request("/api/salary/status")
}

export async function refreshData(): Promise<{ message: string }> {
  return request("/api/refresh-data", { method: "POST" })
}

export async function getPlayers(): Promise<Player[]> {
  return request("/api/players")
}
