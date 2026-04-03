import { ChangeDetectionStrategy, Component, computed, inject } from "@angular/core"
import { RouterLink } from "@angular/router"
import { ActivatedRoute } from "@angular/router"

@Component({
  selector: "app-auth-home-page",
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="hero card">
      <div>
        <p class="eyebrow">Chatbot Access</p>
        <h1>Choose how to authenticate</h1>
        <p class="lede">
          This chat workspace supports standards-based HTTP Basic and Digest, plus a Keycloak-ready
          OAuth2 flow. After login, you choose the transport protocol and enter the protected chat.
        </p>
      </div>
      <div class="hero-note">
        <p class="note-label">Return path</p>
        <p class="note-copy">{{ returnTo() }}</p>
      </div>
    </section>

    <section class="card-grid">
      <article class="card auth-card">
        <p class="eyebrow">HTTP Basic</p>
        <h2>Browser-native credential challenge</h2>
        <p>
          Use a standard Basic auth challenge and store a secured chat session cookie on success.
        </p>
        <a
          class="primary-action"
          [routerLink]="['/auth/basic']"
          [queryParams]="{ returnTo: returnTo() }"
        >
          Continue with Basic
        </a>
      </article>

      <article class="card auth-card">
        <p class="eyebrow">HTTP Digest</p>
        <h2>Challenge-response login</h2>
        <p>
          Use a standards-based Digest challenge, then continue into the protected protocol flow.
        </p>
        <a
          class="primary-action"
          [routerLink]="['/auth/digest']"
          [queryParams]="{ returnTo: returnTo() }"
        >
          Continue with Digest
        </a>
      </article>

      <article class="card auth-card">
        <p class="eyebrow">OAuth2 / Keycloak</p>
        <h2>Keycloak-ready token login</h2>
        <p>
          Use a bearer token flow compatible with a Keycloak-backed Authorization Code with PKCE
          setup.
        </p>
        <a
          class="primary-action"
          [routerLink]="['/auth/oauth2']"
          [queryParams]="{ returnTo: returnTo() }"
        >
          Continue with OAuth2
        </a>
      </article>
    </section>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .card,
      .hero {
        background: rgba(255, 251, 245, 0.78);
        border: 1px solid rgba(16, 35, 61, 0.09);
        border-radius: 28px;
        box-shadow: 0 22px 46px rgba(16, 35, 61, 0.08);
      }
      .hero {
        display: grid;
        grid-template-columns: minmax(0, 1.5fr) minmax(220px, 0.7fr);
        gap: 20px;
        margin-bottom: 24px;
        padding: 28px;
      }
      .card-grid {
        display: grid;
        gap: 20px;
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .auth-card {
        padding: 24px;
        display: grid;
        gap: 14px;
      }
      .eyebrow,
      .note-label {
        margin: 0;
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
      .lede,
      .note-copy,
      p {
        margin: 0;
        line-height: 1.6;
        color: #20415d;
      }
      .hero-note {
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.72);
        padding: 16px;
      }
      .primary-action {
        display: inline-flex;
        justify-content: center;
        align-items: center;
        text-decoration: none;
        border-radius: 999px;
        background: #10233d;
        color: #f8fbfc;
        padding: 12px 18px;
        font-weight: 700;
      }
      .primary-action:focus-visible {
        outline: 3px solid #c45a1b;
        outline-offset: 3px;
      }
      @media (max-width: 980px) {
        .hero,
        .card-grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class AuthHomePage {
  private readonly route = inject(ActivatedRoute)

  protected readonly returnTo = computed(
    () => this.route.snapshot.queryParamMap.get("returnTo") ?? "/chat/protocol",
  )
}
