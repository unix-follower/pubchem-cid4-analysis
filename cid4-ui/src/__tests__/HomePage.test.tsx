import "@testing-library/jest-dom"
import { render, screen } from "@testing-library/react"
import Page from "@/app/page"

describe("Home page", () => {
  test("renders home page", () => {
    // when
    render(<Page />)

    // then
    const main = screen.getByText("To get started, edit the page.tsx file.")
    expect(main).toBeInTheDocument()
  })
})
