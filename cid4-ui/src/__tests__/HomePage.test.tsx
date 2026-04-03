import "@testing-library/jest-dom"

import Page from "@/app/page"

const redirect = jest.fn()

jest.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => redirect(...args),
}))

describe("Home page", () => {
  test("redirects to the auth flow", () => {
    Page()

    expect(redirect).toHaveBeenCalledWith("/auth")
  })
})
