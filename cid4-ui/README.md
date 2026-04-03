This is the React and Next.js client for the secured CID4 chatbot flow.

## Chat Flow

The app mirrors the Angular chatbot implementation against the shared FastAPI backend:

- `/auth` lets the user choose Basic, Digest, or OAuth2 / Keycloak-ready authentication.
- `/chat/protocol` is only available to authenticated users and stores the selected transport.
- `/chat` is the protected chat workspace for HTTP, SSE, and WebSocket generation.

Authentication state and the chosen transport are stored in `sessionStorage`, while the backend remains the source of truth for the secured session cookie and CSRF token.

## Development

First, run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

The client expects the FastAPI backend to expose:

- `/api/auth/me`
- `/api/auth/basic/login`
- `/api/auth/digest/login`
- `/api/auth/session`
- `/api/auth/oauth2/keycloak/config`
- `/api/auth/logout`
- `/api/llm/generate`
- `/api/llm/generate/stream`
- `/ws/llm/generate`

## Validation

```bash
npm test
npm run build
```

## Notes

- The OAuth2 screen supports a development bearer token: `cid4-keycloak-dev-token`.
- Browser redirects for Basic and Digest login are initiated directly so the native auth challenges remain intact.
- Chat output is rendered as plain text to reduce XSS exposure while still supporting streaming updates.

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
