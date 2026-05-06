import { ChangeDetectionStrategy, Component, computed, inject } from "@angular/core"
import { ActivatedRoute, RouterLink } from "@angular/router"

import { AuthSessionService } from "../../core/auth/auth-session.service"

@Component({
  selector: "app-basic-auth-page",
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./basic-auth.page.html",
  styleUrl: "./basic-auth.page.css",
})
export class BasicAuthPage {
  private readonly route = inject(ActivatedRoute)
  private readonly authSession = inject(AuthSessionService)

  protected readonly returnTo = computed(
    () => this.route.snapshot.queryParamMap.get("returnTo") ?? "/chat/protocol",
  )

  protected startLogin(): void {
    this.authSession.startBrowserLogin("basic", this.returnTo())
  }
}
