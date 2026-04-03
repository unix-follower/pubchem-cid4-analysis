"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Suspense } from "react"

export default function AuthPage() {
  return (
    <Suspense fallback={<AuthPageFallback />}>
      <AuthPageContent />
    </Suspense>
  )
}

function AuthPageContent() {
  const searchParams = useSearchParams()
  const returnTo = searchParams.get("returnTo") ?? "/chat/protocol"

  return (
    <>
      <section className="grid gap-5 rounded-[2rem] border border-slate-900/10 bg-white/75 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.08)] md:grid-cols-[1.5fr_0.8fr]">
        <div>
          <p className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
            Chatbot Access
          </p>
          <h1 className="text-4xl font-black tracking-tight text-slate-900 md:text-5xl">
            Choose how to authenticate
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
            This workspace supports standards-based HTTP Basic and Digest, plus a Keycloak-ready
            OAuth2 bearer-token flow. After login, the user chooses HTTP, SSE, or WebSocket before
            entering the protected chat.
          </p>
        </div>

        <div className="rounded-[1.5rem] bg-white/70 p-5">
          <p className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
            Return path
          </p>
          <p className="text-lg font-bold text-slate-900">{returnTo}</p>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Protected backend requests redirect anonymous users to the matching auth screen.
          </p>
        </div>
      </section>

      <section className="grid gap-5 md:grid-cols-3">
        <AuthCard
          href={`/auth/basic?returnTo=${encodeURIComponent(returnTo)}`}
          badge="HTTP Basic"
          title="Browser-native credential challenge"
          copy="Use a standard Basic challenge and store a chat session cookie after successful authentication."
          action="Continue with Basic"
        />
        <AuthCard
          href={`/auth/digest?returnTo=${encodeURIComponent(returnTo)}`}
          badge="HTTP Digest"
          title="Challenge-response login"
          copy="Run a standards-based Digest negotiation, then continue into the protected protocol flow."
          action="Continue with Digest"
        />
        <AuthCard
          href={`/auth/oauth2?returnTo=${encodeURIComponent(returnTo)}`}
          badge="OAuth2 / Keycloak"
          title="Keycloak-ready token login"
          copy="Use a bearer token flow compatible with a Keycloak-backed Authorization Code with PKCE setup."
          action="Continue with OAuth2"
        />
      </section>
    </>
  )
}

function AuthPageFallback() {
  return (
    <section className="grid gap-3 rounded-[2rem] border border-slate-900/10 bg-white/75 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
      <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">Chatbot Access</p>
      <h1 className="text-3xl font-black tracking-tight text-slate-900">
        Preparing authentication routes
      </h1>
      <p className="max-w-2xl leading-7 text-slate-600">
        Resolving the backend return path for the secured chat flow.
      </p>
    </section>
  )
}

function AuthCard({
  href,
  badge,
  title,
  copy,
  action,
}: Readonly<{
  href: string
  badge: string
  title: string
  copy: string
  action: string
}>) {
  return (
    <article className="grid gap-4 rounded-[2rem] border border-slate-900/10 bg-white/75 p-6 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
      <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">{badge}</p>
      <h2 className="text-2xl font-bold text-slate-900">{title}</h2>
      <p className="leading-7 text-slate-600">{copy}</p>
      <Link
        className="inline-flex items-center justify-center rounded-full bg-slate-900 px-5 py-3 font-bold text-white"
        href={href}
      >
        {action}
      </Link>
    </article>
  )
}
