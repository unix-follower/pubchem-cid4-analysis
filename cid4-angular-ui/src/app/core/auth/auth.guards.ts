import { inject } from "@angular/core"
import { CanActivateFn, Router } from "@angular/router"

import { AuthSessionService } from "./auth-session.service"

export const authGuard: CanActivateFn = async (_route, state) => {
  const authSession = inject(AuthSessionService)
  const router = inject(Router)
  const authenticated = await authSession.ensureAuthenticated()

  if (authenticated) {
    return true
  }

  return router.createUrlTree(["/auth"], {
    queryParams: { returnTo: state.url },
  })
}

export const protocolGuard: CanActivateFn = async (_route, state) => {
  const authSession = inject(AuthSessionService)
  const router = inject(Router)
  const authenticated = await authSession.ensureAuthenticated()

  if (!authenticated) {
    return router.createUrlTree(["/auth"], {
      queryParams: { returnTo: state.url },
    })
  }

  if (authSession.selectedProtocol() !== null) {
    return true
  }

  return router.createUrlTree(["/chat/protocol"], {
    queryParams: { returnTo: state.url },
  })
}
