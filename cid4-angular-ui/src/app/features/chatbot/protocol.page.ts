import { ChangeDetectionStrategy, Component, computed, inject } from "@angular/core"
import { ActivatedRoute, Router, RouterLink } from "@angular/router"

import { AuthSessionService } from "../../core/auth/auth-session.service"
import { LlmProtocol } from "../../core/llm/llm-client.service"

@Component({
  selector: "app-protocol-page",
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./protocol.page.html",
  styleUrl: "./protocol.page.css",
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
