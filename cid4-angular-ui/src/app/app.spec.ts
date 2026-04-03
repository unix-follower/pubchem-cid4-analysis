import { provideRouter } from "@angular/router"
import { TestBed } from "@angular/core/testing"
import { App } from "./app"
import { routes } from "./app.routes"

describe("App", () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter(routes)],
    }).compileComponents()
  })

  it("should create the app", () => {
    const fixture = TestBed.createComponent(App)
    const app = fixture.componentInstance
    expect(app).toBeTruthy()
  })

  it("should render the app brand", async () => {
    const fixture = TestBed.createComponent(App)
    await fixture.whenStable()
    const compiled = fixture.nativeElement as HTMLElement
    expect(compiled.querySelector(".brand")?.textContent).toContain("CID 4 Analysis Studio")
  })

  it("should render the chatbot nav link", async () => {
    const fixture = TestBed.createComponent(App)
    await fixture.whenStable()
    const compiled = fixture.nativeElement as HTMLElement
    expect(compiled.querySelector(".primary-nav")?.textContent).toContain("Chatbot")
  })
})
