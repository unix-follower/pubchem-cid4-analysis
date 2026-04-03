import type { ReactNode } from "react"

export default function ChatLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <main className="min-h-screen bg-[linear-gradient(145deg,#f6efe3_0%,#e7f3f3_48%,#dde8df_100%)] px-6 py-10 text-slate-900 md:px-10">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-7xl flex-col gap-6">
        {children}
      </div>
    </main>
  )
}
