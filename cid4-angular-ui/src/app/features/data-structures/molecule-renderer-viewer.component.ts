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
  templateUrl: "./molecule-renderer-viewer.component.html",
  styleUrl: "./molecule-renderer-viewer.component.css",
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
