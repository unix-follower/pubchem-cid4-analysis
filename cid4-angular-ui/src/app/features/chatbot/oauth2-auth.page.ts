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
  template: `
    <section class="card hero">
      <div>
        <p class="eyebrow">OAuth2 / Keycloak</p>
        <h1>Use a Keycloak-ready bearer token flow</h1>
        <p class="lede">
          This screen is wired for a Keycloak-backed Authorization Code with PKCE setup. In the
          current repo it also supports a development bearer token so the protected chat flow is
          usable without a live Keycloak environment.
        </p>
      </div>

      <div class="config-card">
        <p class="config-label">Provider</p>
        <p class="config-value">{{ keycloakConfig()?.provider ?? "keycloak" }}</p>
        <p class="config-meta">Configured: {{ keycloakConfig()?.configured ? "yes" : "no" }}</p>
        <p class="config-meta">Client: {{ keycloakConfig()?.client_id ?? "placeholder" }}</p>
        <p class="config-meta">Realm: {{ keycloakConfig()?.realm ?? "placeholder" }}</p>
      </div>
    </section>

    <section class="card panel">
      <p class="eyebrow">Token login</p>
      <h2>Exchange a bearer token for a chat session</h2>

      <form [formGroup]="form" (ngSubmit)="submit()" class="form-grid">
        <label class="field">
          <span>Access token</span>
          <textarea
            formControlName="token"
            rows="8"
            placeholder="cid4-keycloak-dev-token"
          ></textarea>
        </label>

        <div class="actions">
          <button type="submit" class="primary-action" [disabled]="busy() || form.invalid">
            {{ busy() ? "Signing in…" : "Sign in with token" }}
          </button>
          <a class="ghost-action" [routerLink]="['/auth']" [queryParams]="{ returnTo: returnTo() }"
            >Back</a
          >
        </div>
      </form>

      @if (errorMessage()) {
        <p class="error-banner">{{ errorMessage() }}</p>
      }

      <p class="hint">Development token: cid4-keycloak-dev-token</p>
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
      .hero {
        display: grid;
        grid-template-columns: minmax(0, 1.45fr) minmax(240px, 0.8fr);
        gap: 20px;
      }
      .config-card {
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.72);
        padding: 16px;
      }
      .eyebrow,
      .config-label {
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
      .config-value {
        font-size: 1.2rem;
        font-weight: 800;
      }
      .config-meta,
      .hint {
        color: #20415d;
      }
      .form-grid {
        display: grid;
        gap: 16px;
        margin-top: 8px;
      }
      .field {
        display: grid;
        gap: 8px;
      }
      .field span {
        font-weight: 700;
        color: #20415d;
      }
      textarea {
        width: 100%;
        min-height: 180px;
        border-radius: 18px;
        border: 1px solid rgba(16, 35, 61, 0.14);
        background: rgba(255, 255, 255, 0.92);
        color: #10233d;
        font: inherit;
        padding: 14px 16px;
      }
      .actions {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
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
      .error-banner {
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(155, 41, 72, 0.12);
        color: #7a1738;
        font-weight: 700;
      }
      @media (max-width: 900px) {
        .hero {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
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
