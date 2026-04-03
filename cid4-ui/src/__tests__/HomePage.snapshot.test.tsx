import "@testing-library/jest-dom"
import { render, screen } from "@testing-library/react"

import AuthPage from "@/app/(auth)/auth/page"

jest.mock("next/navigation", () => ({
  useSearchParams: () => ({
    get: (key: string) => (key === "returnTo" ? "/chat/protocol" : null),
  }),
}))

jest.mock("next/link", () => {
  const MockLink = (props: { children?: unknown; href?: string } & Record<string, unknown>) => {
    const { children, href, ...rest } = props

    return (
      <a href={href} {...rest}>
        {children}
      </a>
    )
  }

  MockLink.displayName = "MockLink"
  return MockLink
})

describe("Home page snapshot", () => {
  test("renders the auth landing page", () => {
    render(<AuthPage />)

    expect(screen.getByRole("heading", { name: "Choose how to authenticate" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Continue with Basic" })).toHaveAttribute(
      "href",
      "/auth/basic?returnTo=%2Fchat%2Fprotocol",
    )
    expect(screen.getByRole("link", { name: "Continue with Digest" })).toHaveAttribute(
      "href",
      "/auth/digest?returnTo=%2Fchat%2Fprotocol",
    )
    expect(screen.getByRole("link", { name: "Continue with OAuth2" })).toHaveAttribute(
      "href",
      "/auth/oauth2?returnTo=%2Fchat%2Fprotocol",
    )
  })
})
