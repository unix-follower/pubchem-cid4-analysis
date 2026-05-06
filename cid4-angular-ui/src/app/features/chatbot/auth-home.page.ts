import { ChangeDetectionStrategy, Component, computed, inject } from "@angular/core"
import { RouterLink, ActivatedRoute } from "@angular/router"

@Component({
  selector: "app-auth-home-page",
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./auth-home.page.html",
  styleUrl: "./auth-home.page.css",
})
export class AuthHomePage {
  private readonly route = inject(ActivatedRoute)

  protected readonly returnTo = computed(
    () => this.route.snapshot.queryParamMap.get("returnTo") ?? "/chat/protocol",
  )
}
