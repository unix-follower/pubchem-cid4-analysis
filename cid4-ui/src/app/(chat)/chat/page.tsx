"use client"

import Link from "next/link"
import { useState } from "react"

import { useChatAuth } from "@/lib/chat-auth"
import {
  LlmClient,
  type LlmFramework,
  type LlmGenerateRequest,
  type LlmStreamEvent,
} from "@/lib/llm-client"
import { useRequireProtocol } from "@/lib/use-chat-gates"

type ChatMessageRole = "system" | "assistant" | "user"

interface ChatMessage {
  role: ChatMessageRole
  text: string
}

const initialTranscript: ChatMessage[] = [
  {
    role: "system",
    text: "You are in the protected chat workspace. Responses stream as plain text over the selected transport.",
  },
]

export default function ChatPage() {
  const auth = useChatAuth()
  const { ready } = useRequireProtocol()

  const [busy, setBusy] = useState(false)
  const [framework, setFramework] = useState<LlmFramework>("pytorch")
  const [modelName, setModelName] = useState("cid4_pytorch_gru_lm")
  const [prompt, setPrompt] = useState("CID 4 literature summary:")
  const [maxNewTokens, setMaxNewTokens] = useState(120)
  const [temperature, setTemperature] = useState(0.8)
  const [topK, setTopK] = useState(8)
  const [transcript, setTranscript] = useState<ChatMessage[]>(initialTranscript)
  const [errorMessage, setErrorMessage] = useState("")

  if (!ready) {
    return (
      <section className="grid gap-3 rounded-[2rem] border border-slate-900/10 bg-white/75 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
        <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
          Protected Chat
        </p>
        <h1 className="text-3xl font-black tracking-tight text-slate-900">Restoring workspace</h1>
        <p className="max-w-2xl leading-7 text-slate-600">
          Checking authentication state and selected transport before loading the chat composer.
        </p>
      </section>
    )
  }

  let selectedProtocolLabel = "Unselected"
  if (auth.selectedProtocol === "websocket") {
    selectedProtocolLabel = "WebSocket"
  } else if (auth.selectedProtocol !== null) {
    selectedProtocolLabel = auth.selectedProtocol.toUpperCase()
  }

  const statusLabel = busy
    ? `Streaming over ${selectedProtocolLabel}`
    : `Ready on ${selectedProtocolLabel}`

  const handleSubmit = async (event: { preventDefault: () => void }) => {
    event.preventDefault()
    if (!prompt.trim() || auth.selectedProtocol === null) {
      return
    }

    const client = new LlmClient(auth)
    const request: LlmGenerateRequest = {
      framework,
      prompt: prompt.trim(),
      model_name: modelName.trim(),
      max_new_tokens: maxNewTokens,
      temperature,
      top_k: topK,
    }

    setBusy(true)
    setErrorMessage("")
    setTranscript((messages): ChatMessage[] => [
      ...messages,
      { role: "user", text: request.prompt },
    ])

    let assistantIndex = -1

    try {
      await client.generate(auth.selectedProtocol, request, (llmEvent: LlmStreamEvent) => {
        if (llmEvent.event === "start") {
          setTranscript((messages): ChatMessage[] => {
            const nextMessages: ChatMessage[] = [...messages, { role: "assistant", text: "" }]
            assistantIndex = nextMessages.length - 1
            return nextMessages
          })
          return
        }

        if (llmEvent.event === "token") {
          setTranscript((messages): ChatMessage[] => {
            if (assistantIndex < 0 || !messages[assistantIndex]) {
              return messages
            }

            const nextMessages = [...messages]
            nextMessages[assistantIndex] = {
              ...nextMessages[assistantIndex],
              text:
                llmEvent.generated_text ??
                `${nextMessages[assistantIndex].text}${llmEvent.text ?? ""}`,
            }
            return nextMessages
          })
          return
        }

        if (llmEvent.event === "complete") {
          setTranscript((messages): ChatMessage[] => {
            if (assistantIndex < 0 || !messages[assistantIndex]) {
              return [...messages, { role: "assistant", text: llmEvent.generated_text ?? "" }]
            }

            const nextMessages = [...messages]
            nextMessages[assistantIndex] = {
              ...nextMessages[assistantIndex],
              text: llmEvent.generated_text ?? nextMessages[assistantIndex].text,
            }
            return nextMessages
          })
          return
        }

        if (llmEvent.event === "error") {
          setErrorMessage(llmEvent.error?.message ?? "Generation failed.")
        }
      })
    } finally {
      setBusy(false)
    }
  }

  const handleLogout = () => {
    auth.logout().catch(() => undefined)
  }

  return (
    <>
      <section className="grid gap-5 rounded-[2rem] border border-slate-900/10 bg-white/75 p-8 shadow-[0_24px_64px_rgba(15,23,42,0.08)] md:grid-cols-[1.5fr_0.9fr]">
        <div>
          <p className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
            Protected Chat
          </p>
          <h1 className="text-4xl font-black tracking-tight text-slate-900 md:text-5xl">
            Authenticated LLM workspace
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
            Prompts and streamed responses stay behind the selected auth method. Output is rendered
            as plain text to reduce XSS risk while still supporting progressive transport updates.
          </p>
        </div>

        <dl className="grid gap-3 md:grid-cols-3 md:gap-4">
          <div className="rounded-[1.5rem] bg-white/70 p-4">
            <dt className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
              User
            </dt>
            <dd className="text-lg font-bold text-slate-900">{auth.username ?? "Unknown user"}</dd>
          </div>
          <div className="rounded-[1.5rem] bg-white/70 p-4">
            <dt className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
              Auth
            </dt>
            <dd className="text-lg font-bold text-slate-900">{auth.authMethod ?? "unknown"}</dd>
          </div>
          <div className="rounded-[1.5rem] bg-white/70 p-4">
            <dt className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
              Protocol
            </dt>
            <dd className="text-lg font-bold text-slate-900">{selectedProtocolLabel}</dd>
          </div>
        </dl>
      </section>

      <section className="grid gap-6 lg:grid-cols-[430px_1fr]">
        <article className="rounded-[2rem] border border-slate-900/10 bg-white/75 p-6 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
          <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
                Composer
              </p>
              <h2 className="mt-2 text-2xl font-bold text-slate-900">Send a protected prompt</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                className="rounded-full border border-slate-900/10 bg-white px-4 py-2 font-bold text-slate-700"
                href="/chat/protocol?returnTo=/chat"
              >
                Change protocol
              </Link>
              <button
                className="rounded-full border border-slate-900/10 bg-white px-4 py-2 font-bold text-slate-700"
                onClick={handleLogout}
                type="button"
              >
                Logout
              </button>
            </div>
          </div>

          <form className="grid gap-4" onSubmit={handleSubmit}>
            <div className="flex flex-wrap gap-2" aria-label="Framework selector">
              <button
                className={`rounded-full px-4 py-2 font-bold ${framework === "pytorch" ? "bg-slate-900 text-white" : "border border-slate-900/10 bg-white text-slate-700"}`}
                onClick={() => {
                  setFramework("pytorch")
                  setModelName("cid4_pytorch_gru_lm")
                }}
                type="button"
              >
                PyTorch
              </button>
              <button
                className={`rounded-full px-4 py-2 font-bold ${framework === "tensorflow" ? "bg-slate-900 text-white" : "border border-slate-900/10 bg-white text-slate-700"}`}
                onClick={() => {
                  setFramework("tensorflow")
                  setModelName("cid4_tensorflow_gru_lm")
                }}
                type="button"
              >
                TensorFlow
              </button>
            </div>

            <label className="grid gap-2 text-sm font-semibold text-slate-700">
              <span>Model name</span>
              <input
                className="rounded-[1.25rem] border border-slate-900/10 bg-white px-4 py-3"
                onChange={(event) => setModelName(event.target.value)}
                type="text"
                value={modelName}
              />
            </label>

            <label className="grid gap-2 text-sm font-semibold text-slate-700">
              <span>Prompt</span>
              <textarea
                className="min-h-44 rounded-[1.5rem] border border-slate-900/10 bg-white px-4 py-3"
                onChange={(event) => setPrompt(event.target.value)}
                rows={8}
                value={prompt}
              />
            </label>

            <div className="grid gap-4 md:grid-cols-3">
              <label className="grid gap-2 text-sm font-semibold text-slate-700">
                <span>Max new tokens</span>
                <input
                  className="rounded-[1.25rem] border border-slate-900/10 bg-white px-4 py-3"
                  max={400}
                  min={1}
                  onChange={(event) => setMaxNewTokens(Number(event.target.value))}
                  type="number"
                  value={maxNewTokens}
                />
              </label>
              <label className="grid gap-2 text-sm font-semibold text-slate-700">
                <span>Temperature</span>
                <input
                  className="rounded-[1.25rem] border border-slate-900/10 bg-white px-4 py-3"
                  max={5}
                  min={0}
                  onChange={(event) => setTemperature(Number(event.target.value))}
                  step={0.1}
                  type="number"
                  value={temperature}
                />
              </label>
              <label className="grid gap-2 text-sm font-semibold text-slate-700">
                <span>Top-k</span>
                <input
                  className="rounded-[1.25rem] border border-slate-900/10 bg-white px-4 py-3"
                  max={128}
                  min={0}
                  onChange={(event) => setTopK(Number(event.target.value))}
                  type="number"
                  value={topK}
                />
              </label>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                className="rounded-full bg-slate-900 px-5 py-3 font-bold text-white disabled:cursor-not-allowed disabled:opacity-70"
                disabled={busy || !prompt.trim()}
                type="submit"
              >
                {busy ? "Generating..." : "Send prompt"}
              </button>
              <button
                className="rounded-full border border-slate-900/10 bg-white px-5 py-3 font-bold text-slate-700"
                disabled={busy}
                onClick={() => {
                  setTranscript(initialTranscript)
                  setErrorMessage("")
                }}
                type="button"
              >
                Clear transcript
              </button>
            </div>
          </form>

          {errorMessage ? (
            <p className="mt-4 rounded-[1rem] bg-rose-100 px-4 py-3 font-semibold text-rose-700">
              {errorMessage}
            </p>
          ) : null}
        </article>

        <article className="rounded-[2rem] border border-slate-900/10 bg-white/75 p-6 shadow-[0_24px_64px_rgba(15,23,42,0.08)]">
          <div className="mb-5">
            <p className="text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
              Transcript
            </p>
            <h2 className="mt-2 text-2xl font-bold text-slate-900">{statusLabel}</h2>
          </div>

          <div aria-live="polite" className="grid max-h-[680px] gap-3 overflow-auto">
            {transcript.map((message, index) => {
              let messageClass = "bg-white"
              if (message.role === "user") {
                messageClass = "bg-amber-100/70"
              } else if (message.role === "assistant") {
                messageClass = "bg-slate-900/5"
              }

              return (
                <article
                  className={`rounded-[1.5rem] px-5 py-4 ${messageClass}`}
                  key={`${message.role}-${index}`}
                >
                  <p className="mb-2 text-xs font-bold tracking-[0.24em] text-amber-700 uppercase">
                    {message.role}
                  </p>
                  <p className="leading-7 whitespace-pre-wrap text-slate-700">{message.text}</p>
                </article>
              )
            })}
          </div>
        </article>
      </section>
    </>
  )
}
