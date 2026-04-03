"use client"

import { useEffect, useState } from "react"
import { usePathname, useRouter } from "next/navigation"

import { useChatAuth } from "./chat-auth"

export function useRequireAuthentication() {
  const auth = useChatAuth()
  const router = useRouter()
  const pathname = usePathname()
  const [ready, setReady] = useState(auth.authState.status === "authenticated")

  useEffect(() => {
    let active = true

    void auth.ensureAuthenticated().then((ok) => {
      if (!active) {
        return
      }

      if (!ok) {
        const returnTo = pathname.startsWith("/chat") ? pathname : "/chat/protocol"
        router.replace(`/auth?returnTo=${encodeURIComponent(returnTo)}`)
        return
      }

      setReady(true)
    })

    return () => {
      active = false
    }
  }, [auth, pathname, router])

  return { ready, auth }
}

export function useRequireProtocol() {
  const router = useRouter()
  const result = useRequireAuthentication()

  useEffect(() => {
    if (result.ready && result.auth.selectedProtocol === null) {
      router.replace("/chat/protocol?returnTo=/chat")
    }
  }, [result.auth.selectedProtocol, result.ready, router])

  return {
    ...result,
    ready: result.ready && result.auth.selectedProtocol !== null,
  }
}
