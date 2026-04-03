import { Injectable, computed, inject, signal } from "@angular/core"
import { Router } from "@angular/router"

type LlmProtocol = "http" | "sse" | "websocket"

export type AuthMethod = "basic" | "digest" | "oauth2"

interface AuthUser {
  username: string
  auth_method: AuthMethod
}

interface AuthState {
  status: "unknown" | "anonymous" | "authenticated"
  user: AuthUser | null
  csrfToken: string | null
}

interface SessionPayload {
  authenticated: boolean
  user?: AuthUser
  csrf_token?: string | null
}

@Injectable({ providedIn: "root" })
export class AuthSessionService {
  private readonly router = inject(Router)
  private readonly authStateSignal = signal<AuthState>(loadAuthState())
  private readonly selectedProtocolSignal = signal<LlmProtocol | null>(loadSelectedProtocol())
  private restorePromise: Promise<boolean> | null = null

  readonly authState = computed(() => this.authStateSignal())
  readonly selectedProtocol = computed(() => this.selectedProtocolSignal())
  readonly isAuthenticated = computed(() => this.authStateSignal().status === "authenticated")
  readonly username = computed(() => this.authStateSignal().user?.username ?? null)
  readonly authMethod = computed(() => this.authStateSignal().user?.auth_method ?? null)
  readonly csrfToken = computed(() => this.authStateSignal().csrfToken)

  async ensureAuthenticated(): Promise<boolean> {
    if (this.authStateSignal().status === "authenticated") {
      return true
    }

    return this.restoreSession()
  }

  async restoreSession(force = false): Promise<boolean> {
    if (!force && this.restorePromise !== null) {
      return this.restorePromise
    }

    if (!force && this.authStateSignal().status === "authenticated") {
      return true
    }

    this.restorePromise = this.fetchApi("/api/auth/me", { method: "GET" })
      .then(async (response) => {
        if (response.status === 200) {
          const payload = (await response.json()) as SessionPayload
          this.setAuthenticated(payload)
          return true
        }
        this.setAnonymous()
        return false
      })
      .catch(() => {
        this.setAnonymous()
        return false
      })
      .finally(() => {
        this.restorePromise = null
      })

    return this.restorePromise
  }

  async loginWithOAuth2Token(
    accessToken: string,
  ): Promise<{ ok: boolean; message: string | null }> {
    const response = await this.fetchApi("/api/auth/session", {
      method: "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-CID4-Auth-Method": "oauth2",
      },
    })

    if (response.status !== 200) {
      const payload = (await response.json().catch(() => null)) as {
        error?: { message?: string }
      } | null
      return {
        ok: false,
        message: payload?.error?.message ?? "OAuth2 login failed.",
      }
    }

    this.setAuthenticated((await response.json()) as SessionPayload)
    return { ok: true, message: null }
  }

  startBrowserLogin(method: Extract<AuthMethod, "basic" | "digest">, returnTo: string): void {
    if (globalThis.window === undefined) {
      return
    }

    const url = new URL(`/api/auth/${method}/login`, globalThis.window.location.origin)
    url.searchParams.set("returnTo", returnTo)
    globalThis.window.location.assign(url.toString())
  }

  async logout(): Promise<void> {
    const headers = new Headers()
    if (this.csrfToken()) {
      headers.set("X-CSRF-Token", this.csrfToken() ?? "")
    }
    await this.fetchApi("/api/auth/logout", { method: "POST", headers })
    this.setAnonymous()
    this.setSelectedProtocol(null)
    await this.router.navigateByUrl("/auth")
  }

  setSelectedProtocol(protocol: LlmProtocol | null): void {
    this.selectedProtocolSignal.set(protocol)
    persistSelectedProtocol(protocol)
  }

  async fetchApi(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
    if (globalThis.window === undefined) {
      return new Response(null, { status: 401 })
    }

    const method = (init.method ?? "GET").toUpperCase()
    const headers = new Headers(init.headers)
    if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS" && this.csrfToken()) {
      headers.set("X-CSRF-Token", this.csrfToken() ?? "")
    }

    const response = await fetch(input, {
      ...init,
      credentials: "same-origin",
      redirect: "manual",
      headers,
    })

    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get("Location")
      if (location) {
        void this.router.navigateByUrl(location)
      }
    }

    if (response.status === 401) {
      this.setAnonymous()
    }

    return response
  }

  private setAuthenticated(payload: SessionPayload): void {
    if (!payload.authenticated || !payload.user) {
      this.setAnonymous()
      return
    }

    const nextState: AuthState = {
      status: "authenticated",
      user: payload.user,
      csrfToken: payload.csrf_token ?? null,
    }
    this.authStateSignal.set(nextState)
    persistAuthState(nextState)
  }

  private setAnonymous(): void {
    const nextState: AuthState = {
      status: "anonymous",
      user: null,
      csrfToken: null,
    }
    this.authStateSignal.set(nextState)
    persistAuthState(nextState)
  }
}

function loadAuthState(): AuthState {
  if (globalThis.window === undefined) {
    return { status: "unknown", user: null, csrfToken: null }
  }

  const rawValue = globalThis.window.sessionStorage.getItem("cid4.auth-state")
  if (!rawValue) {
    return { status: "unknown", user: null, csrfToken: null }
  }

  try {
    const parsed = JSON.parse(rawValue) as AuthState
    if (parsed.status === "authenticated" || parsed.status === "anonymous") {
      return parsed
    }
  } catch {
    return { status: "unknown", user: null, csrfToken: null }
  }

  return { status: "unknown", user: null, csrfToken: null }
}

function persistAuthState(state: AuthState): void {
  if (globalThis.window === undefined) {
    return
  }

  globalThis.window.sessionStorage.setItem("cid4.auth-state", JSON.stringify(state))
}

function loadSelectedProtocol(): LlmProtocol | null {
  if (globalThis.window === undefined) {
    return null
  }

  const rawValue = globalThis.window.sessionStorage.getItem("cid4.selected-protocol")
  return rawValue === "http" || rawValue === "sse" || rawValue === "websocket" ? rawValue : null
}

function persistSelectedProtocol(protocol: LlmProtocol | null): void {
  if (globalThis.window === undefined) {
    return
  }

  if (protocol === null) {
    globalThis.window.sessionStorage.removeItem("cid4.selected-protocol")
    return
  }

  globalThis.window.sessionStorage.setItem("cid4.selected-protocol", protocol)
}
