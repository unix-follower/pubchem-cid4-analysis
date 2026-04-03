"use client"

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { useRouter } from "next/navigation"

import type { LlmProtocol } from "./llm-client"

export type AuthMethod = "basic" | "digest" | "oauth2"

export interface AuthUser {
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

export interface KeycloakConfig {
  configured: boolean
  provider: string
  authorization_endpoint: string | null
  realm: string | null
  client_id: string | null
  redirect_uri: string | null
}

interface ChatAuthContextValue {
  authState: AuthState
  selectedProtocol: LlmProtocol | null
  isAuthenticated: boolean
  username: string | null
  authMethod: AuthMethod | null
  csrfToken: string | null
  ensureAuthenticated: () => Promise<boolean>
  restoreSession: (force?: boolean) => Promise<boolean>
  loginWithOAuth2Token: (accessToken: string) => Promise<{ ok: boolean; message: string | null }>
  startBrowserLogin: (method: Extract<AuthMethod, "basic" | "digest">, returnTo: string) => void
  logout: () => Promise<void>
  setSelectedProtocol: (protocol: LlmProtocol | null) => void
  fetchApi: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
}

const ChatAuthContext = createContext<ChatAuthContextValue | null>(null)

export function ChatAuthProvider({ children }: Readonly<{ children: ReactNode }>) {
  const router = useRouter()
  const restorePromiseRef = useRef<Promise<boolean> | null>(null)
  const initialSelectedProtocol = loadSelectedProtocol()
  const [authState, setAuthState] = useState<AuthState>(loadAuthState)
  const [selectedProtocol, setSelectedProtocolState] = useState(initialSelectedProtocol)

  useEffect(() => {
    persistAuthState(authState)
  }, [authState])

  useEffect(() => {
    persistSelectedProtocol(selectedProtocol)
  }, [selectedProtocol])

  const setAnonymous = () => {
    setAuthState({ status: "anonymous", user: null, csrfToken: null })
  }

  const setAuthenticated = (payload: SessionPayload) => {
    if (!payload.authenticated || !payload.user) {
      setAnonymous()
      return
    }

    setAuthState({
      status: "authenticated",
      user: payload.user,
      csrfToken: payload.csrf_token ?? null,
    })
  }

  const fetchApi = async (input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> => {
    if (globalThis.window === undefined) {
      return new Response(null, { status: 401 })
    }

    const method = (init.method ?? "GET").toUpperCase()
    const headers = new Headers(init.headers)
    const csrfToken = authState.csrfToken

    if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS" && csrfToken) {
      headers.set("X-CSRF-Token", csrfToken)
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
        router.replace(location)
      }
    }

    if (response.status === 401) {
      setAnonymous()
    }

    return response
  }

  const restoreSession = async (force = false): Promise<boolean> => {
    if (!force && restorePromiseRef.current !== null) {
      return restorePromiseRef.current
    }

    if (!force && authState.status === "authenticated") {
      return true
    }

    const nextPromise = fetchApi("/api/auth/me", { method: "GET" })
      .then(async (response) => {
        if (response.status === 200) {
          setAuthenticated((await response.json()) as SessionPayload)
          return true
        }

        setAnonymous()
        return false
      })
      .catch(() => {
        setAnonymous()
        return false
      })
      .finally(() => {
        restorePromiseRef.current = null
      })

    restorePromiseRef.current = nextPromise
    return nextPromise
  }

  const ensureAuthenticated = async () => {
    if (authState.status === "authenticated") {
      return true
    }

    return restoreSession()
  }

  const loginWithOAuth2Token = async (accessToken: string) => {
    const response = await fetchApi("/api/auth/session", {
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

    setAuthenticated((await response.json()) as SessionPayload)
    return { ok: true, message: null }
  }

  const startBrowserLogin = (method: Extract<AuthMethod, "basic" | "digest">, returnTo: string) => {
    if (globalThis.window === undefined) {
      return
    }

    const url = new URL(`/api/auth/${method}/login`, globalThis.window.location.origin)
    url.searchParams.set("returnTo", returnTo)
    globalThis.window.location.assign(url.toString())
  }

  const logout = async () => {
    const headers = new Headers()
    if (authState.csrfToken) {
      headers.set("X-CSRF-Token", authState.csrfToken)
    }

    await fetchApi("/api/auth/logout", { method: "POST", headers })
    setAnonymous()
    setSelectedProtocolState(null)
    router.replace("/auth")
  }

  const value = useMemo<ChatAuthContextValue>(
    () => ({
      authState,
      selectedProtocol,
      isAuthenticated: authState.status === "authenticated",
      username: authState.user?.username ?? null,
      authMethod: authState.user?.auth_method ?? null,
      csrfToken: authState.csrfToken,
      ensureAuthenticated,
      restoreSession,
      loginWithOAuth2Token,
      startBrowserLogin,
      logout,
      setSelectedProtocol: setSelectedProtocolState,
      fetchApi,
    }),
    [authState, ensureAuthenticated, fetchApi, loginWithOAuth2Token, logout, restoreSession, selectedProtocol],
  )

  return <ChatAuthContext.Provider value={value}>{children}</ChatAuthContext.Provider>
}

export function useChatAuth() {
  const value = useContext(ChatAuthContext)

  if (value === null) {
    throw new Error("useChatAuth must be used within a ChatAuthProvider")
  }

  return value
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

function persistAuthState(state: AuthState) {
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

function persistSelectedProtocol(protocol: LlmProtocol | null) {
  if (globalThis.window === undefined) {
    return
  }

  if (protocol === null) {
    globalThis.window.sessionStorage.removeItem("cid4.selected-protocol")
    return
  }

  globalThis.window.sessionStorage.setItem("cid4.selected-protocol", protocol)
}
