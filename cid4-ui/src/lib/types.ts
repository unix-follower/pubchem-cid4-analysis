export interface ChatAuthContextValue {
  fetchApi: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
}
