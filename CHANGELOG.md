# Changelog

## 1.0.0 — Unreleased

Upgrade from published 0.1.1: Python minimum 3.7 → 3.10; Requests minimum 2.0 → 2.34.2; default origin api.nstproxy.com → api.nstdata.io. HTTP connect/read timeouts and a per-response decoded-body cap are now enabled; redirects are rejected. HTTP/API/transport failures now raise safe `NstDataApiError` instead of raw Requests or generic exceptions. Existing package/import names, positional token and public task methods remain available. The v1 routes and `x-api-key` header already existed in 0.1.1 and are retained. Review these compatibility changes before upgrading.

- Shared safe errors, streaming limits and response cleanup for API and deferred storage reads.
- Validate known response scalar types before constructing result DTOs; preserve null optional fields and ignore unknown fields.
- Report deeply nested JSON and request-header encoding failures through safe SDK errors.
- Separate quick start from bilingual task, pagination, content and configuration guides; resolve repository documentation links in package metadata.
- Public source-confirmed routes, encoded IDs, opaque cursor/ref handling and forward-compatible DTO fields.
- Preserve failed/missing/empty content and private-field safety.
- Decode inline Base64 PDF/screenshots and UTF-8 raw text through the existing byte getters, retaining empty content and inline-over-reference precedence.
- Validate optional content references, links and known metadata types before exposing result DTOs.
- Correct request DTO and action-helper annotations to use integer API milliseconds and scroll coordinates; document server timeout and JS wait bounds. Serialization and fractional local HTTP timeouts are unchanged.
- Keep quick-start and bounded examples from treating missing Markdown as a successful empty body; remove site-specific demonstration selectors.
- Preserve optional task `id` and content `truncated` without changing existing positional DTO arguments; reject malformed inline content and truncation flags with safe errors.
- Bounded known-ID polling and page iteration, without task creation retries or an asyncio claim.
- Offline/mocked and loopback HTTP regressions; wheel/sdist and clean-install checks.
- Exercise installed-wheel regressions outside the source tree and document the required build dependency.
- Use SPDX MIT metadata and an explicit license file with setuptools 77+; retain the existing license text.
