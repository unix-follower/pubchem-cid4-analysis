import { ChangeDetectionStrategy, Component, computed, inject } from "@angular/core"
import { ActivatedRoute, RouterLink } from "@angular/router"

import { AuthSessionService } from "../../core/auth/auth-session.service"

@Component({
  selector: "app-digest-auth-page",
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./digest-auth.page.html",
  styleUrl: "./digest-auth.page.css",
})
export class DigestAuthPage {
  private readonly route = inject(ActivatedRoute)
  private readonly authSession = inject(AuthSessionService)

  protected readonly returnTo = computed(
    () => this.route.snapshot.queryParamMap.get("returnTo") ?? "/chat/protocol",
  )

  protected startLogin(): void {
    this.authSession.startBrowserLogin("digest", this.returnTo())
  }
}
