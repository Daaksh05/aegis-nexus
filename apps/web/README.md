# Aegis Nexus Web

The Next.js App Router frontend requires Node.js 24 and npm.

```sh
npm ci
npm run dev
```

Run the checks from `apps/web`:

```sh
npm run lint
npm run typecheck
npm test
```

Create a production build with `npm run build`.

Regenerate the typed API client after changing the API contract:

```sh
npm run generate:api
```

From the repository root, `make contracts` exports the FastAPI OpenAPI spec and
generates the web client types. Change the API, run `make contracts`, and commit
`packages/contracts/openapi.json` and `apps/web/src/lib/api/schema.d.ts` together.
