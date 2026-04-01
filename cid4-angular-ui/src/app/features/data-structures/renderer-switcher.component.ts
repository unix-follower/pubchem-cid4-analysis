import { ChangeDetectionStrategy, Component, input, output } from "@angular/core"

import { RendererKind, RendererSwitchOption } from "../../core/renderer/renderer.types"

@Component({
  selector: "app-renderer-switcher",
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="switcher" role="radiogroup" aria-label="Graphics renderer">
      @for (option of options(); track option.kind) {
        <button
          type="button"
          class="chip"
          [class.active]="currentRenderer() === option.kind"
          [class.unsupported]="!option.supported"
          [disabled]="!option.supported"
          [attr.aria-pressed]="currentRenderer() === option.kind"
          (click)="rendererSelected.emit(option.kind)"
        >
          {{ option.label }}
          @if (!option.supported) {
            <span class="chip-note">Unavailable</span>
          }
        </button>
      }

      <button type="button" class="chip ghost" (click)="resetView.emit()">Reset view</button>
    </div>
  `,
  styles: [
    `
      .switcher {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }

      .chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: 0;
        border-radius: 999px;
        padding: 11px 16px;
        font: inherit;
        font-weight: 700;
        color: #10233d;
        background: #dbeaf1;
        cursor: pointer;
      }

      .chip.active {
        background: #10233d;
        color: #f8fbfc;
      }

      .chip.unsupported {
        background: #ece5dc;
        color: #6d7f94;
      }

      .chip.ghost {
        background: #f2e8da;
      }

      .chip:disabled {
        cursor: not-allowed;
        opacity: 0.72;
      }

      .chip-note {
        font-size: 0.8rem;
        font-weight: 600;
      }
    `,
  ],
})
export class RendererSwitcherComponent {
  readonly currentRenderer = input.required<RendererKind>()
  readonly options = input.required<RendererSwitchOption[]>()

  readonly rendererSelected = output<RendererKind>()
  readonly resetView = output<void>()
}
