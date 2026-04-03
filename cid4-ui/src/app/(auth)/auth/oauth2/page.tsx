"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useEffect, useState } from "react"

import type { KeycloakConfig } from "@/lib/chat-auth"
import { useChatAuth } from "@/lib/chat-auth"

export default function OAuth2AuthPage() {
  return (
    <Suspense fallback={<OAuthFallback />}>
      <OAuth2AuthPageContent />
    </Suspense>
  )
}

function OAuth2AuthPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const auth = useChatAuth()
  const returnTo = searchParams.get("returnTo") ?? "/chat/protocol"

  const [token, setToken] = useState("cid4-keycloak-dev-token")
  const [busy, setBusy] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")
  const [keycloakConfig, setKeycloakConfig] = useState<KeycloakConfig | null>(null)

  useEffect(() => {
    let active = true

    void fetch("/api/auth/oauth2/keycloak/config")
      .then(async (response) => {
        if (!response.ok) {
          return
        }

        const payload = (await response.json()) as KeycloakConfig
        if (active) {
          setKeycloakConfig(payload)
        }
      })
      .catch(() => undefined)

    return () => {
      active = false
    }
  }, [])

  const handleSubmit = async (event: { preventDefault: () => void }) => {
    event.preventDefault()
    if (!token.trim()) {
      return
    }

    setBusy(true)
    setErrorMessage("")
    const result = await auth.loginWithOAuth2Token(token.trim())
    setBusy(false)

    if (!result.ok) {
      setErrorMessage(result.message ?? "OAuth2 login failed.")
      return
    }

    router.replace(returnTo)
  }

  return (
    <>
      <section className="grid gap-5 rounded-[2rem] border border-slate-900/10 bg-white/75 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.08)] md:grid-cols-[1.45fr_0.8fr]">
        <div>
          <p className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
            OAuth2 / Keycloak
          </p>
          <h1 className="text-4xl font-black tracking-tight text-slate-900">
            Use a Keycloak-ready bearer token flow
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
            This screen is wired for a Keycloak-backed Authorization Code with PKCE setup. In the
            current repo it also supports a development bearer token so the protected chat flow is
            usable without a live Keycloak environment.
          </p>
        </div>

        <div className="rounded-[1.5rem] bg-white/70 p-5">
          <p className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
            Provider
          </p>
          <p className="text-xl font-black text-slate-900">
            {keycloakConfig?.provider ?? "keycloak"}
          </p>
          <p className="mt-2 text-sm text-slate-600">
            Configured: {keycloakConfig?.configured ? "yes" : "no"}
          </p>
          <p className="text-sm text-slate-600">
            Client: {keycloakConfig?.client_id ?? "placeholder"}
          </p>
          <p className="text-sm text-slate-600">Realm: {keycloakConfig?.realm ?? "placeholder"}</p>
        </div>
      </section>

      <section className="grid gap-4 rounded-[2rem] border border-slate-900/10 bg-white/75 p-6 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
        <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">Token login</p>
        <h2 className="text-2xl font-bold text-slate-900">
          Exchange a bearer token for a chat session
        </h2>

        <form className="grid gap-4" onSubmit={handleSubmit}>
          <label className="grid gap-2 text-sm font-semibold text-slate-700">
            <span>Access token</span>
            <textarea
              className="min-h-48 rounded-[1.5rem] border border-slate-900/10 bg-white px-4 py-3 text-base font-medium text-slate-900"
              onChange={(event) => setToken(event.target.value)}
              placeholder="cid4-keycloak-dev-token"
              rows={8}
              value={token}
            />
          </label>

          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-full bg-slate-900 px-5 py-3 font-bold text-white disabled:cursor-not-allowed disabled:opacity-70"
              disabled={busy || !token.trim()}
              type="submit"
            >
              {busy ? "Signing in..." : "Sign in with token"}
            </button>
            <Link
              className="rounded-full border border-slate-900/10 bg-white px-5 py-3 font-bold text-slate-700"
              href={`/auth?returnTo=${encodeURIComponent(returnTo)}`}
            >
              Back
            </Link>
          </div>
        </form>

        {errorMessage ? (
          <p className="rounded-[1rem] bg-rose-100 px-4 py-3 font-semibold text-rose-700">
            {errorMessage}
          </p>
        ) : null}

        <p className="text-sm text-slate-600">Development token: cid4-keycloak-dev-token</p>
      </section>
    </>
  )
}

function OAuthFallback() {
  return (
    <section className="grid gap-3 rounded-[2rem] border border-slate-900/10 bg-white/75 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
      <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
        OAuth2 / Keycloak
      </p>
      <h1 className="text-3xl font-black tracking-tight text-slate-900">Preparing token login</h1>
      <p className="max-w-2xl leading-7 text-slate-600">
        Loading the return path and Keycloak-ready configuration details.
      </p>
    </section>
  )
}
