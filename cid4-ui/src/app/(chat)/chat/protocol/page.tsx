"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense } from "react"

import type { LlmProtocol } from "@/lib/llm-client"
import { useRequireAuthentication } from "@/lib/use-chat-gates"

const protocols = [
  {
    id: "http",
    badge: "Simple",
    title: "HTTP",
    copy: "Single request-response interaction with the protected FastAPI backend.",
  },
  {
    id: "sse",
    badge: "Streaming",
    title: "SSE",
    copy: "One-way streamed tokens over Server-Sent Events for progressive text rendering.",
  },
  {
    id: "websocket",
    badge: "Duplex",
    title: "WebSocket",
    copy: "Bidirectional transport ready for future cancellation and interactive control messages.",
  },
] as const satisfies ReadonlyArray<{
  id: LlmProtocol
  badge: string
  title: string
  copy: string
}>

export default function ProtocolPage() {
  return (
    <Suspense
      fallback={
        <LoadingCard
          label="Restoring session"
          message="Checking your secured chat session before protocol selection."
        />
      }
    >
      <ProtocolPageContent />
    </Suspense>
  )
}

function ProtocolPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { auth, ready } = useRequireAuthentication()
  const returnTo = searchParams.get("returnTo") ?? "/chat"

  if (!ready) {
    return (
      <LoadingCard
        label="Restoring session"
        message="Checking your secured chat session before protocol selection."
      />
    )
  }

  return (
    <>
      <section className="grid gap-5 rounded-[2rem] border border-slate-900/10 bg-white/75 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.08)] md:grid-cols-[1.4fr_0.8fr]">
        <div>
          <p className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
            Protocol Selection
          </p>
          <h1 className="text-4xl font-black tracking-tight text-slate-900">
            Choose how the model should respond
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
            Pick the transport once for this chat session. The workspace streams partial output over
            SSE or WebSocket, or uses a single request-response cycle over plain HTTP.
          </p>
        </div>

        <div className="rounded-[1.5rem] bg-white/70 p-5">
          <p className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
            Signed in as
          </p>
          <p className="text-xl font-black text-slate-900">{auth.username ?? "Unknown user"}</p>
          <p className="mt-2 text-sm text-slate-600">Method: {auth.authMethod ?? "unknown"}</p>
        </div>
      </section>

      <section className="grid gap-5 md:grid-cols-3">
        {protocols.map((protocol) => (
          <article
            className="grid gap-4 rounded-[2rem] border border-slate-900/10 bg-white/75 p-6 shadow-[0_24px_64px_rgba(15,23,42,0.08)]"
            key={protocol.id}
          >
            <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
              {protocol.badge}
            </p>
            <h2 className="text-2xl font-bold text-slate-900">{protocol.title}</h2>
            <p className="leading-7 text-slate-600">{protocol.copy}</p>
            <button
              className="rounded-full bg-slate-900 px-5 py-3 font-bold text-white"
              onClick={() => {
                auth.setSelectedProtocol(protocol.id)
                router.replace(returnTo)
              }}
              type="button"
            >
              Use {protocol.title}
            </button>
          </article>
        ))}
      </section>

      <section className="rounded-[2rem] border border-slate-900/10 bg-white/75 p-6 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
        <Link
          className="inline-flex rounded-full border border-slate-900/10 bg-white px-5 py-3 font-bold text-slate-700"
          href="/auth"
        >
          Switch auth method
        </Link>
      </section>
    </>
  )
}

function LoadingCard({ label, message }: Readonly<{ label: string; message: string }>) {
  return (
    <section className="grid gap-3 rounded-[2rem] border border-slate-900/10 bg-white/75 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
      <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">{label}</p>
      <h1 className="text-3xl font-black tracking-tight text-slate-900">Secured chat access</h1>
      <p className="max-w-2xl leading-7 text-slate-600">{message}</p>
    </section>
  )
}
