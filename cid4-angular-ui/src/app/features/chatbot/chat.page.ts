import { ChangeDetectionStrategy, Component, computed, inject, signal } from "@angular/core"
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms"
import { RouterLink } from "@angular/router"

import { AuthSessionService } from "../../core/auth/auth-session.service"
import { LlmClientService, LlmFramework } from "../../core/llm/llm-client.service"

type ChatMessageRole = "system" | "assistant" | "user"

interface ChatMessage {
  role: ChatMessageRole
  text: string
}

@Component({
  selector: "app-chat-page",
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="hero card">
      <div>
        <p class="eyebrow">Protected Chat</p>
        <h1>Authenticated LLM workspace</h1>
        <p class="lede">
          Prompts and streamed responses stay behind the selected auth method. Output is rendered as
          plain text to reduce XSS risk while still supporting progressive transport updates.
        </p>
      </div>

      <div class="status-grid">
        <div>
          <dt>User</dt>
          <dd>{{ authSession.username() ?? "Unknown user" }}</dd>
        </div>
        <div>
          <dt>Auth</dt>
          <dd>{{ authSession.authMethod() ?? "unknown" }}</dd>
        </div>
        <div>
          <dt>Protocol</dt>
          <dd>{{ selectedProtocolLabel() }}</dd>
        </div>
      </div>
    </section>

    <section class="workspace-grid">
      <article class="card composer-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Composer</p>
            <h2>Send a protected prompt</h2>
          </div>
          <div class="toolbar">
            <a
              class="ghost-action"
              [routerLink]="['/chat/protocol']"
              [queryParams]="{ returnTo: '/chat/workspace' }"
              >Change protocol</a
            >
            <button type="button" class="ghost-action" (click)="logout()">Logout</button>
          </div>
        </div>

        <form class="form-grid" [formGroup]="form" (ngSubmit)="submitPrompt()">
          <div class="toggle-group" aria-label="Framework selector">
            <button
              type="button"
              class="chip"
              [class.active]="framework() === 'pytorch'"
              (click)="setFramework('pytorch')"
            >
              PyTorch
            </button>
            <button
              type="button"
              class="chip"
              [class.active]="framework() === 'tensorflow'"
              (click)="setFramework('tensorflow')"
            >
              TensorFlow
            </button>
          </div>

          <label class="field">
            <span>Model name</span>
            <input type="text" formControlName="modelName" />
          </label>

          <label class="field">
            <span>Prompt</span>
            <textarea rows="8" formControlName="prompt"></textarea>
          </label>

          <div class="settings-grid">
            <label class="field compact">
              <span>Max new tokens</span>
              <input type="number" formControlName="maxNewTokens" min="1" max="400" />
            </label>
            <label class="field compact">
              <span>Temperature</span>
              <input type="number" formControlName="temperature" min="0" max="5" step="0.1" />
            </label>
            <label class="field compact">
              <span>Top-k</span>
              <input type="number" formControlName="topK" min="0" max="128" />
            </label>
          </div>

          <div class="actions">
            <button type="submit" class="primary-action" [disabled]="busy() || form.invalid">
              {{ busy() ? "Generating…" : "Send prompt" }}
            </button>
            <button
              type="button"
              class="ghost-action"
              [disabled]="busy()"
              (click)="clearTranscript()"
            >
              Clear transcript
            </button>
          </div>
        </form>

        @if (errorMessage()) {
          <p class="error-banner">{{ errorMessage() }}</p>
        }
      </article>

      <article class="card transcript-card">
        <div class="card-header">
          <div>
            <p class="eyebrow">Transcript</p>
            <h2>{{ statusLabel() }}</h2>
          </div>
        </div>

        <div class="transcript" aria-live="polite">
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
      .status-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
      }
      .status-grid div,
      .message {
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.72);
        padding: 14px 16px;
      }
      dt,
      .message-role,
      .eyebrow {
        margin: 0 0 6px;
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8b6325;
      }
      dd,
      .message-body,
      .lede,
      p {
        margin: 0;
        line-height: 1.6;
        color: #10233d;
      }
      .workspace-grid {
        display: grid;
        gap: 24px;
        grid-template-columns: minmax(0, 430px) minmax(0, 1fr);
      }
      .card {
        padding: 24px;
      }
      .card-header {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: start;
        margin-bottom: 18px;
      }
      .toolbar,
      .toggle-group,
      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      .form-grid {
        display: grid;
        gap: 16px;
      }
      .settings-grid {
        display: grid;
        gap: 14px;
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .field {
        display: grid;
        gap: 8px;
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
        min-height: 176px;
        resize: vertical;
      }
      .chip,
      .primary-action,
      .ghost-action {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        font-weight: 700;
        padding: 11px 16px;
      }
      .chip,
      .ghost-action {
        border: 1px solid rgba(16, 35, 61, 0.14);
        background: rgba(255, 255, 255, 0.8);
        color: #20415d;
        text-decoration: none;
      }
      .chip.active,
      .primary-action {
        border: none;
        background: #10233d;
        color: #f8fbfc;
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
      .error-banner {
        margin-top: 16px;
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(155, 41, 72, 0.12);
        color: #7a1738;
        font-weight: 700;
      }
      @media (max-width: 980px) {
        .hero,
        .workspace-grid,
        .settings-grid,
        .status-grid {
          grid-template-columns: 1fr;
        }
        .card-header {
          flex-direction: column;
        }
      }
    `,
  ],
})
export class ChatPage {
  private readonly formBuilder = inject(FormBuilder)
  private readonly llmClient = inject(LlmClientService)

  protected readonly authSession = inject(AuthSessionService)
  protected readonly busy = signal(false)
  protected readonly framework = signal<LlmFramework>("pytorch")
  protected readonly transcript = signal<ChatMessage[]>([
    {
      role: "system",
      text: "You are in the protected chat workspace. Responses stream as plain text over the selected transport.",
    },
  ])
  protected readonly errorMessage = signal("")
  protected readonly form = this.formBuilder.nonNullable.group({
    modelName: ["cid4_pytorch_gru_lm", [Validators.required]],
    prompt: ["CID 4 literature summary:", [Validators.required]],
    maxNewTokens: [120, [Validators.required, Validators.min(1), Validators.max(400)]],
    temperature: [0.8, [Validators.required, Validators.min(0), Validators.max(5)]],
    topK: [8, [Validators.required, Validators.min(0), Validators.max(128)]],
  })

  protected readonly selectedProtocolLabel = computed(() => {
    const protocol = this.authSession.selectedProtocol()
    if (protocol === null) {
      return "Unselected"
    }
    return protocol === "websocket" ? "WebSocket" : protocol.toUpperCase()
  })

  protected readonly statusLabel = computed(() => {
    if (this.busy()) {
      return `Streaming over ${this.selectedProtocolLabel()}`
    }
    return `Ready on ${this.selectedProtocolLabel()}`
  })

  protected setFramework(framework: LlmFramework): void {
    this.framework.set(framework)
    this.form.patchValue({
      modelName: framework === "tensorflow" ? "cid4_tensorflow_gru_lm" : "cid4_pytorch_gru_lm",
    })
  }

  protected async submitPrompt(): Promise<void> {
    if (this.form.invalid || this.authSession.selectedProtocol() === null) {
      return
    }

    const value = this.form.getRawValue()
    this.busy.set(true)
    this.errorMessage.set("")
    this.transcript.update((messages) => [...messages, { role: "user", text: value.prompt.trim() }])

    let assistantIndex = -1

    try {
      await this.llmClient.generate(
        this.authSession.selectedProtocol() ?? "http",
        {
          framework: this.framework(),
          prompt: value.prompt.trim(),
          model_name: value.modelName.trim(),
          max_new_tokens: value.maxNewTokens,
          temperature: value.temperature,
          top_k: value.topK,
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
    } finally {
      this.busy.set(false)
    }
  }

  protected clearTranscript(): void {
    this.transcript.set([
      {
        role: "system",
        text: "You are in the protected chat workspace. Responses stream as plain text over the selected transport.",
      },
    ])
    this.errorMessage.set("")
  }

  protected async logout(): Promise<void> {
    await this.authSession.logout()
  }
}
