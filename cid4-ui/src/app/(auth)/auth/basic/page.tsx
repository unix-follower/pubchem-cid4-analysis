"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Suspense } from "react"

import { useChatAuth } from "@/lib/chat-auth"

export default function BasicAuthPage() {
  return (
    <Suspense
      fallback={
        <AuthFallback label="HTTP Basic" message="Loading the Basic authentication challenge." />
      }
    >
      <BasicAuthPageContent />
    </Suspense>
  )
}

function BasicAuthPageContent() {
  const searchParams = useSearchParams()
  const auth = useChatAuth()
  const returnTo = searchParams.get("returnTo") ?? "/chat/protocol"

  return (
    <>
      <section className="grid gap-5 rounded-[2rem] border border-slate-900/10 bg-white/75 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.08)] md:grid-cols-[1.4fr_0.8fr]">
        <div>
          <p className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
            HTTP Basic
          </p>
          <h1 className="text-4xl font-black tracking-tight text-slate-900">
            Authenticate with a browser challenge
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
            The backend issues a standard Basic challenge. The browser handles the credential
            prompt, then FastAPI stores the chat session and returns the user to the protected flow.
          </p>
        </div>

        <dl className="grid gap-3">
          <div className="rounded-[1.5rem] bg-white/70 p-4">
            <dt className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
              Demo username
            </dt>
            <dd className="text-lg font-bold text-slate-900">analyst</dd>
          </div>
          <div className="rounded-[1.5rem] bg-white/70 p-4">
            <dt className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
              Demo password
            </dt>
            <dd className="text-lg font-bold text-slate-900">cid4-basic-password</dd>
          </div>
        </dl>
      </section>

      <section className="grid gap-4 rounded-[2rem] border border-slate-900/10 bg-white/75 p-6 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
        <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">Next step</p>
        <h2 className="text-2xl font-bold text-slate-900">Start the challenge</h2>
        <p className="leading-7 text-slate-600">
          The login completes on the backend and redirects to {returnTo} on success.
        </p>
        <div className="flex flex-wrap gap-3">
          <button
            className="rounded-full bg-slate-900 px-5 py-3 font-bold text-white"
            onClick={() => auth.startBrowserLogin("basic", returnTo)}
            type="button"
          >
            Start Basic login
          </button>
          <Link
            className="rounded-full border border-slate-900/10 bg-white px-5 py-3 font-bold text-slate-700"
            href={`/auth?returnTo=${encodeURIComponent(returnTo)}`}
          >
            Back
          </Link>
        </div>
      </section>
    </>
  )
}

function AuthFallback({ label, message }: Readonly<{ label: string; message: string }>) {
  return (
    <section className="grid gap-3 rounded-[2rem] border border-slate-900/10 bg-white/75 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
      <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">{label}</p>
      <h1 className="text-3xl font-black tracking-tight text-slate-900">Preparing sign-in</h1>
      <p className="max-w-2xl leading-7 text-slate-600">{message}</p>
    </section>
  )
}
