# PR 100 - Document Store HTML Cache Rule

## Branch

`pr_100_document-caddy-cache`

## Purpose

Preserve the production Caddy rule added after PR 099 verification so future
server maintenance does not reintroduce a blank Clover return page after a web
deployment.

## Documentation

- Add the live `/` and `/index.html` no-cache matcher to the reference Caddy
  block.
- Explain why Store payment returns must not reuse an older HTML document.
- Record the required Caddy validation and reload commands.
- Clarify that hashed assets retain their normal caching behavior.
- Clarify in `.env.example` that `N8N_WEBHOOK_SECRET` must match the n8n
  `X-Webhook-Secret` credential and that the real value must not be committed.

## Runtime impact

None. This PR changes documentation only. The matching rule is already active
and verified on the production VPS.

## Verification

- `git diff --check`
