import { ChangeDetectionStrategy, Component, computed, inject } from "@angular/core"
import { ActivatedRoute, RouterLink } from "@angular/router"

import { AuthSessionService } from "../../core/auth/auth-session.service"

@Component({
  selector: "app-basic-auth-page",
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="card hero">
      <div>
        <p class="eyebrow">HTTP Basic</p>
        <h1>Authenticate with a browser challenge</h1>
        <p class="lede">
          The backend will issue a standard Basic challenge. Your browser handles the credential
          prompt, then FastAPI stores the chat session and returns you to the protected flow.
        </p>
      </div>

      <dl class="credentials">
        <div>
          <dt>Demo username</dt>
          <dd>analyst</dd>
        </div>
        <div>
          <dt>Demo password</dt>
          <dd>cid4-basic-password</dd>
        </div>
      </dl>
    </section>

    <section class="card panel">
      <p class="eyebrow">Next step</p>
      <h2>Start the challenge</h2>
      <p>The login completes on the backend and redirects to {{ returnTo() }} on success.</p>
      <div class="actions">
        <button type="button" class="primary-action" (click)="startLogin()">
          Start Basic login
        </button>
        <a class="ghost-action" [routerLink]="['/auth']" [queryParams]="{ returnTo: returnTo() }"
          >Back</a
        >
      </div>
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
        grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.8fr);
        gap: 20px;
      }
      .credentials {
        display: grid;
        gap: 12px;
        margin: 0;
      }
      .credentials div {
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.72);
        padding: 14px 16px;
      }
      .eyebrow,
      dt {
        margin: 0 0 6px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8b6325;
      }
      h1,
      h2,
      dd,
      p {
        margin: 0;
        color: #10233d;
        line-height: 1.6;
      }
      .actions {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-top: 16px;
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
      @media (max-width: 900px) {
        .hero {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
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
