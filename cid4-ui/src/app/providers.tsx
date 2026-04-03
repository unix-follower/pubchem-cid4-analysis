"use client"

import { ReactNode } from "react"

import { ChatAuthProvider } from "@/lib/chat-auth"

export function AppProviders({ children }: Readonly<{ children: ReactNode }>) {
  return <ChatAuthProvider>{children}</ChatAuthProvider>
}
