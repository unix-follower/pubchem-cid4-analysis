import { ChangeDetectionStrategy, Component, input, output } from "@angular/core"

import { RendererKind, RendererSwitchOption } from "../../core/renderer/renderer.types"

@Component({
  selector: "app-renderer-switcher",
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./renderer-switcher.component.html",
  styleUrl: "./renderer-switcher.component.css",
})
export class RendererSwitcherComponent {
  readonly currentRenderer = input.required<RendererKind>()
  readonly options = input.required<RendererSwitchOption[]>()

  readonly rendererSelected = output<RendererKind>()
  readonly resetView = output<void>()
}
