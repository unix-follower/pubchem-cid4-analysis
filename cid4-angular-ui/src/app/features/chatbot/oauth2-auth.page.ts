import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from "@angular/core"
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms"
import { ActivatedRoute, Router, RouterLink } from "@angular/router"

import { AuthSessionService } from "../../core/auth/auth-session.service"

interface KeycloakConfig {
  configured: boolean
  provider: string
  authorization_endpoint: string | null
  realm: string | null
  client_id: string | null
  redirect_uri: string | null
}

@Component({
  selector: "app-oauth2-auth-page",
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./oauth2-auth.page.html",
  styleUrl: "./oauth2-auth.page.css",
})
export class OAuth2AuthPage implements OnInit {
  private readonly formBuilder = inject(FormBuilder)
  private readonly route = inject(ActivatedRoute)
  private readonly router = inject(Router)
  private readonly authSession = inject(AuthSessionService)

  protected readonly form = this.formBuilder.nonNullable.group({
    token: ["cid4-keycloak-dev-token", [Validators.required]],
  })
  protected readonly busy = signal(false)
  protected readonly errorMessage = signal("")
  protected readonly keycloakConfig = signal<KeycloakConfig | null>(null)
  protected readonly returnTo = computed(
    () => this.route.snapshot.queryParamMap.get("returnTo") ?? "/chat/protocol",
  )

  protected async submit(): Promise<void> {
    if (this.form.invalid) {
      return
    }

    this.busy.set(true)
    this.errorMessage.set("")
    const result = await this.authSession.loginWithOAuth2Token(this.form.getRawValue().token.trim())
    this.busy.set(false)

    if (!result.ok) {
      this.errorMessage.set(result.message ?? "OAuth2 login failed.")
      return
    }

    await this.router.navigateByUrl(this.returnTo())
  }

  private async loadConfig(): Promise<void> {
    if (globalThis.window === undefined) {
      return
    }

    const response = await fetch("/api/auth/oauth2/keycloak/config")
    if (!response.ok) {
      return
    }
    this.keycloakConfig.set((await response.json()) as KeycloakConfig)
  }

  ngOnInit(): void {
    void this.loadConfig()
  }
}
