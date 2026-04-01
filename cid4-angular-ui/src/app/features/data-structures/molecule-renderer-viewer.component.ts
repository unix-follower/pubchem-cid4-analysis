import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  afterNextRender,
  computed,
  effect,
  inject,
  input,
  viewChild,
} from "@angular/core"

import { MoleculeComparisonSummary } from "../../core/cid4/comparison"
import { MoleculeGraph } from "../../core/cid4/types"
import { MoleculeRendererService } from "../../core/renderer/molecule-renderer.service"
import { RendererSwitcherComponent } from "./renderer-switcher.component"

@Component({
  selector: "app-molecule-renderer-viewer",
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RendererSwitcherComponent],
  template: `
    <div class="viewer-header">
      <div>
        <p class="eyebrow">Renderer Strategy</p>
        <h3>WebGL / WebGPU viewer</h3>
      </div>

      <app-renderer-switcher
        [currentRenderer]="rendererService.currentRenderer()"
        [options]="rendererService.switchOptions()"
        (rendererSelected)="switchRenderer($event)"
        (resetView)="resetView()"
      />
    </div>

    @if (statusMessage(); as message) {
      <p
        class="status-banner"
        [class.status-warning]="isWarning()"
        [class.status-error]="isError()"
      >
        {{ message }}
      </p>
    }

    @if (molecule(); as activeMolecule) {
      <div class="viewer-metrics">
        <span>{{ rendererService.currentRenderer().toUpperCase() }}</span>
        <span>{{ activeMolecule.atoms.length }} atoms</span>
        <span>{{ activeMolecule.bonds.length }} bonds</span>
        <span>Render {{ renderDurationLabel() }}</span>
      </div>
    }

    @if (comparisonSummary(); as summary) {
      <div class="comparison-banner">
        <span>Overlay vs {{ comparisonReferenceLabel() ?? "reference" }}</span>
        <span>Mean displacement {{ summary.meanAtomDisplacement.toFixed(3) }}</span>
        <span>Max displacement {{ summary.maxAtomDisplacement.toFixed(3) }}</span>
        <span>Max bond delta {{ summary.maxBondLengthDelta.toFixed(3) }}</span>
      </div>
    }

    <div #host class="viewer-host" role="img" aria-label="Strategy-based molecular renderer"></div>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .viewer-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        margin-bottom: 16px;
      }

      .eyebrow {
        margin: 0 0 6px;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8b6325;
      }

      h3 {
        margin: 0;
        font-size: 1.2rem;
      }

      .status-banner {
        margin: 0 0 14px;
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(16, 35, 61, 0.06);
        color: #28415d;
      }

      .status-warning {
        background: #fff3cf;
        color: #5c4d11;
      }

      .status-error {
        background: #fce3df;
        color: #7d2418;
      }

      .viewer-metrics {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 14px;
      }

      .viewer-metrics span {
        padding: 8px 11px;
        border-radius: 999px;
        background: rgba(16, 35, 61, 0.05);
        font-weight: 700;
        color: #38516f;
      }

      .comparison-banner {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 14px;
      }

      .comparison-banner span {
        padding: 8px 11px;
        border-radius: 999px;
        background: rgba(196, 90, 27, 0.12);
        color: #7a3d17;
        font-weight: 700;
      }

      .viewer-host {
        min-height: 420px;
        border-radius: 24px;
        background:
          radial-gradient(circle at top left, rgba(244, 211, 163, 0.42), transparent 28%),
          linear-gradient(180deg, #fcfaf5 0%, #eef5f7 100%);
        box-shadow: inset 0 0 0 1px rgba(16, 35, 61, 0.08);
      }

      @media (max-width: 860px) {
        .viewer-header {
          flex-direction: column;
        }
      }
    `,
  ],
})
export class MoleculeRendererViewerComponent {
  readonly molecule = input<MoleculeGraph | null>(null)
  readonly comparisonReference = input<MoleculeGraph | null>(null)
  readonly comparisonSummary = input<MoleculeComparisonSummary | null>(null)
  readonly comparisonReferenceLabel = input<string | null>(null)

  protected readonly rendererService = inject(MoleculeRendererService)

  private readonly destroyRef = inject(DestroyRef)
  private readonly hostRef = viewChild<ElementRef<HTMLDivElement>>("host")

  protected readonly statusMessage = computed(() => this.rendererService.status().message)
  protected readonly isWarning = computed(() => this.rendererService.status().phase === "fallback")
  protected readonly isError = computed(() => this.rendererService.status().phase === "error")
  protected readonly renderDurationLabel = computed(() => {
    const duration = this.rendererService.metrics().lastRenderDurationMs
    return duration === null ? "pending" : `${duration.toFixed(1)} ms`
  })

  constructor() {
    afterNextRender(() => {
      const host = this.hostRef()?.nativeElement

      if (!host) {
        return
      }

      void this.rendererService.attachHost(host)
    })

    effect(() => {
      void this.rendererService.setMolecule(this.molecule())
    })

    effect(() => {
      void this.rendererService.setComparisonReference(this.comparisonReference())
    })

    this.destroyRef.onDestroy(() => {
      this.rendererService.dispose()
    })
  }

  protected switchRenderer(kind: "webgl" | "webgpu"): void {
    void this.rendererService.switchRenderer(kind)
  }

  protected resetView(): void {
    this.rendererService.resetView()
  }
}
