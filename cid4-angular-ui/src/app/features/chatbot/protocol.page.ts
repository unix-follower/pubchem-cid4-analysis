import { ChangeDetectionStrategy, Component, computed, inject } from "@angular/core"
import { ActivatedRoute, Router, RouterLink } from "@angular/router"

import { AuthSessionService } from "../../core/auth/auth-session.service"
import { LlmProtocol } from "../../core/llm/llm-client.service"

@Component({
  selector: "app-protocol-page",
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card hero">
      <div>
        <p class="eyebrow">Protocol Selection</p>
        <h1>Choose how the model should respond</h1>
        <p class="lede">
          Pick the transport once for this chat session. The workspace will stream partial output
          over SSE or WebSocket, or use a single request-response cycle over plain HTTP.
        </p>
      </div>

      <div class="session-card">
        <p class="session-label">Signed in as</p>
        <p class="session-value">{{ authSession.username() ?? "Unknown user" }}</p>
        <p class="session-meta">Method: {{ authSession.authMethod() ?? "unknown" }}</p>
      </div>
    </section>

    <section class="protocol-grid">
      @for (protocol of protocols; track protocol.id) {
        <article class="card protocol-card">
          <p class="eyebrow">{{ protocol.badge }}</p>
          <h2>{{ protocol.title }}</h2>
          <p>{{ protocol.copy }}</p>
          <button type="button" class="primary-action" (click)="selectProtocol(protocol.id)">
            Use {{ protocol.title }}
          </button>
        </article>
      }
    </section>

    <section class="card footer-card">
      <a class="ghost-action" [routerLink]="['/auth']">Switch auth method</a>
    </section>
  `,
  styles: [
    `
      :host {
        display: grid;
        gap: 24px;
      }
      .card {
        background: rgba(255, 251, 245, 0.78);
        border: 1px solid rgba(16, 35, 61, 0.09);
        border-radius: 28px;
        box-shadow: 0 22px 46px rgba(16, 35, 61, 0.08);
        padding: 24px;
      }
      .hero,
      .protocol-grid {
        display: grid;
        gap: 20px;
      }
      .hero {
        grid-template-columns: minmax(0, 1.4fr) minmax(240px, 0.8fr);
      }
      .protocol-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .protocol-card {
        display: grid;
        gap: 12px;
      }
      .session-card {
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.72);
        padding: 16px;
      }
      .eyebrow,
      .session-label {
        margin: 0 0 6px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8b6325;
      }
      h1,
      h2,
      p {
        margin: 0;
        color: #10233d;
        line-height: 1.6;
      }
      .session-value {
        font-size: 1.2rem;
        font-weight: 800;
      }
      .primary-action,
      .ghost-action {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        border-radius: 999px;
        padding: 12px 18px;
        font-weight: 700;
        text-decoration: none;
      }
      .primary-action {
        border: none;
        background: #10233d;
        color: #f8fbfc;
      }
      .ghost-action {
        border: 1px solid rgba(16, 35, 61, 0.12);
        color: #20415d;
        background: rgba(255, 255, 255, 0.7);
      }
      @media (max-width: 980px) {
        .hero,
        .protocol-grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class ProtocolPage {
  private readonly router = inject(Router)
  private readonly route = inject(ActivatedRoute)

  protected readonly authSession = inject(AuthSessionService)
  protected readonly returnTo = computed(
    () => this.route.snapshot.queryParamMap.get("returnTo") ?? "/chat/workspace",
  )
  protected readonly protocols = [
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
  ] as const

  protected async selectProtocol(protocol: LlmProtocol): Promise<void> {
    this.authSession.setSelectedProtocol(protocol)
    await this.router.navigateByUrl(this.returnTo())
  }
}
