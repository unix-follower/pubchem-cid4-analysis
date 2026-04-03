import { CommonModule } from "@angular/common"
import { ChangeDetectionStrategy, Component, computed, inject, signal } from "@angular/core"
import { FormsModule } from "@angular/forms"

import { LlmClientService, LlmFramework, LlmProtocol } from "../../core/llm/llm-client.service"

type ChatMessageRole = "system" | "assistant" | "user"

interface ChatMessage {
  role: ChatMessageRole
  text: string
}

@Component({
  selector: "app-llm-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="hero card" aria-labelledby="llm-title">
      <div>
        <p class="eyebrow">LLM Protocol Lab</p>
        <h1 id="llm-title">Switch between HTTP, SSE, and WebSocket generation</h1>
        <p class="lede">
          Use the same FastAPI LLM backend with three delivery modes. The protocol toggle changes
          transport only; the prompt, framework, and generation settings stay shared.
        </p>
      </div>

      <dl class="hero-meta">
        <div>
          <dt>Protocol</dt>
          <dd>{{ protocol().toUpperCase() }}</dd>
        </div>
        <div>
          <dt>Framework</dt>
          <dd>{{ framework() }}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{{ statusLabel() }}</dd>
        </div>
      </dl>
    </section>

    <section class="workspace-grid llm-grid">
      <article class="card composer-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Prompt</p>
            <h2>Transport-aware generation</h2>
          </div>
        </div>

        <div class="toggle-group" aria-label="Protocol selector">
          <button
            type="button"
            class="chip"
            [class.active]="protocol() === 'http'"
            (click)="setProtocol('http')"
          >
            HTTP
          </button>
          <button
            type="button"
            class="chip"
            [class.active]="protocol() === 'sse'"
            (click)="setProtocol('sse')"
          >
            SSE
          </button>
          <button
            type="button"
            class="chip"
            [class.active]="protocol() === 'websocket'"
            (click)="setProtocol('websocket')"
          >
            WebSocket
          </button>
        </div>

        <div class="toggle-group" aria-label="Framework selector">
          <button
            type="button"
            class="chip ghost"
            [class.active]="framework() === 'pytorch'"
            (click)="setFramework('pytorch')"
          >
            PyTorch
          </button>
          <button
            type="button"
            class="chip ghost"
            [class.active]="framework() === 'tensorflow'"
            (click)="setFramework('tensorflow')"
          >
            TensorFlow
          </button>
        </div>

        <label class="field">
          <span>Model name</span>
          <input [(ngModel)]="modelName" placeholder="cid4_pytorch_gru_lm" />
        </label>

        <label class="field">
          <span>Prompt</span>
          <textarea
            [(ngModel)]="prompt"
            rows="8"
            placeholder="CID 4 literature summary:"
          ></textarea>
        </label>

        <div class="settings-grid">
          <label class="field compact">
            <span>Max new tokens</span>
            <input type="number" [(ngModel)]="maxNewTokens" min="1" max="400" />
          </label>
          <label class="field compact">
            <span>Temperature</span>
            <input type="number" [(ngModel)]="temperature" min="0" max="5" step="0.1" />
          </label>
          <label class="field compact">
            <span>Top-k</span>
            <input type="number" [(ngModel)]="topK" min="0" max="128" />
          </label>
        </div>

        <div class="actions">
          <button type="button" class="primary-action" [disabled]="busy()" (click)="submitPrompt()">
            {{ busy() ? "Generating…" : "Generate" }}
          </button>
          <button type="button" class="chip ghost" [disabled]="busy()" (click)="clearTranscript()">
            Clear transcript
          </button>
        </div>

        @if (errorMessage()) {
          <p class="error-banner">{{ errorMessage() }}</p>
        }
      </article>

      <article class="card transcript-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Transcript</p>
            <h2>Shared prompt, switched transport</h2>
          </div>
        </div>

        <div class="transcript">
          @for (message of transcript(); track $index) {
            <article
              class="message"
              [class.assistant]="message.role === 'assistant'"
              [class.user]="message.role === 'user'"
            >
              <p class="message-role">{{ message.role }}</p>
              <p class="message-body">{{ message.text }}</p>
            </article>
          }
        </div>
      </article>
    </section>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .hero,
      .card {
        background: rgba(255, 251, 245, 0.78);
        border: 1px solid rgba(16, 35, 61, 0.09);
        border-radius: 28px;
        box-shadow: 0 22px 46px rgba(16, 35, 61, 0.08);
      }

      .hero {
        display: grid;
        grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.9fr);
        gap: 20px;
        padding: 28px;
        margin-bottom: 24px;
      }

      .hero-meta {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
        margin: 0;
      }

      .hero-meta div,
      .message {
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.72);
        padding: 14px 16px;
      }

      .hero-meta dt,
      .message-role {
        margin: 0 0 6px;
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8b6325;
      }

      .hero-meta dd,
      .message-body,
      .lede {
        margin: 0;
        line-height: 1.6;
      }

      .workspace-grid {
        display: grid;
        gap: 24px;
      }

      .llm-grid {
        grid-template-columns: minmax(0, 440px) minmax(0, 1fr);
      }

      .card {
        padding: 24px;
      }

      .card-header {
        margin-bottom: 18px;
      }

      .eyebrow {
        margin: 0 0 6px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8b6325;
      }

      h1,
      h2 {
        margin: 0;
        color: #10233d;
      }

      .toggle-group,
      .actions,
      .settings-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }

      .settings-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }

      .field {
        display: grid;
        gap: 8px;
        margin-top: 16px;
      }

      .field span {
        font-weight: 700;
        color: #20415d;
      }

      input,
      textarea {
        width: 100%;
        border: 1px solid rgba(16, 35, 61, 0.14);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.92);
        color: #10233d;
        font: inherit;
        padding: 14px 16px;
      }

      textarea {
        resize: vertical;
        min-height: 176px;
      }

      .chip,
      .primary-action {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        border: 1px solid rgba(16, 35, 61, 0.14);
        background: rgba(255, 255, 255, 0.8);
        color: #20415d;
        font: inherit;
        font-weight: 700;
        padding: 11px 16px;
        cursor: pointer;
      }

      .chip.active,
      .primary-action {
        background: #10233d;
        color: #f8fbfc;
      }

      .chip.ghost.active {
        background: #c45a1b;
        border-color: #c45a1b;
        color: #fff6ee;
      }

      .primary-action[disabled],
      .chip[disabled] {
        cursor: not-allowed;
        opacity: 0.68;
      }

      .actions {
        margin-top: 18px;
      }

      .error-banner {
        margin: 16px 0 0;
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(155, 41, 72, 0.12);
        color: #7a1738;
        font-weight: 700;
      }

      .transcript {
        display: grid;
        gap: 12px;
        max-height: 680px;
        overflow: auto;
      }

      .message.user {
        background: rgba(196, 90, 27, 0.1);
      }

      .message.assistant {
        background: rgba(16, 35, 61, 0.08);
      }

      @media (max-width: 980px) {
        .hero,
        .llm-grid,
        .settings-grid {
          grid-template-columns: 1fr;
        }

        .hero-meta {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class LlmPage {
  private readonly llmClient = inject(LlmClientService)

  protected readonly protocol = signal<LlmProtocol>("http")
  protected readonly framework = signal<LlmFramework>("pytorch")
  protected readonly busy = signal(false)
  protected readonly transcript = signal<ChatMessage[]>([
    {
      role: "system",
      text: "Choose a protocol, send a prompt, and compare how the same FastAPI LLM response arrives over HTTP, SSE, or WebSocket.",
    },
  ])
  protected readonly errorMessage = signal("")

  protected prompt = "CID 4 literature summary:"
  protected modelName = "cid4_pytorch_gru_lm"
  protected maxNewTokens = 120
  protected temperature = 0.8
  protected topK = 8

  protected readonly statusLabel = computed(() => {
    if (this.busy()) {
      return `Streaming via ${this.protocol().toUpperCase()}`
    }
    return "Idle"
  })

  protected setProtocol(protocol: LlmProtocol): void {
    this.protocol.set(protocol)
    this.errorMessage.set("")
  }

  protected setFramework(framework: LlmFramework): void {
    this.framework.set(framework)
    this.errorMessage.set("")
    if (framework === "tensorflow" && this.modelName === "cid4_pytorch_gru_lm") {
      this.modelName = "cid4_tensorflow_gru_lm"
    }
    if (framework === "pytorch" && this.modelName === "cid4_tensorflow_gru_lm") {
      this.modelName = "cid4_pytorch_gru_lm"
    }
  }

  protected async submitPrompt(): Promise<void> {
    const trimmedPrompt = this.prompt.trim()
    if (!trimmedPrompt) {
      this.errorMessage.set("Prompt must not be empty.")
      return
    }

    this.busy.set(true)
    this.errorMessage.set("")
    this.transcript.update((messages) => [...messages, { role: "user", text: trimmedPrompt }])
    let assistantIndex = -1

    await this.llmClient.generate(
      this.protocol(),
      {
        framework: this.framework(),
        prompt: trimmedPrompt,
        model_name: this.modelName.trim() || "cid4_pytorch_gru_lm",
        max_new_tokens: this.maxNewTokens,
        temperature: this.temperature,
        top_k: this.topK,
      },
      (event) => {
        if (event.event === "start") {
          this.transcript.update((messages) => {
            const nextMessages: ChatMessage[] = [...messages, { role: "assistant", text: "" }]
            assistantIndex = nextMessages.length - 1
            return nextMessages
          })
          return
        }

        if (event.event === "token") {
          this.transcript.update((messages) => {
            if (assistantIndex < 0 || !messages[assistantIndex]) {
              return messages
            }
            const nextMessages = [...messages]
            nextMessages[assistantIndex] = {
              ...nextMessages[assistantIndex],
              text:
                event.generated_text ?? `${nextMessages[assistantIndex].text}${event.text ?? ""}`,
            }
            return nextMessages
          })
          return
        }

        if (event.event === "complete") {
          this.transcript.update((messages) => {
            if (assistantIndex < 0 || !messages[assistantIndex]) {
              return [...messages, { role: "assistant", text: event.generated_text ?? "" }]
            }
            const nextMessages = [...messages]
            nextMessages[assistantIndex] = {
              ...nextMessages[assistantIndex],
              text: event.generated_text ?? nextMessages[assistantIndex].text,
            }
            return nextMessages
          })
          return
        }

        if (event.event === "error") {
          this.errorMessage.set(event.error?.message ?? "Generation failed.")
        }
      },
    )

    this.busy.set(false)
  }

  protected clearTranscript(): void {
    this.transcript.set([
      {
        role: "system",
        text: "Choose a protocol, send a prompt, and compare how the same FastAPI LLM response arrives over HTTP, SSE, or WebSocket.",
      },
    ])
    this.errorMessage.set("")
  }
}
