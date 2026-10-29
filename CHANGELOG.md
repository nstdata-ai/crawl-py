# Changelog

## 1.0.0

### Compatibility

- Require Python 3.10+ and Requests 2.34.2+; the default API origin is now `api.nstdata.io`.
- HTTP, API and transport failures raise safe `NstDataApiError` instances. Connection/read timeouts and response-size limits are enabled; redirects are rejected.
- Existing package/import names, positional token arguments and public task methods remain available. The v1 routes and `x-api-key` header are retained.

### Changes

- Support bounded task polling and cursor pagination without automatic creation retries.
- Validate task IDs and response types while preserving task identity, optional metadata and service truncation.
- Read inline and referenced content, keeping absent, empty and failed results distinct; decode binary Base64 and UTF-8 data without silently replacing invalid content.
- Close streamed responses and sessions, protect credentials and report safe errors for malformed responses.
- Provide executable bilingual workflows, isolated wheel/sdist checks and SPDX MIT package metadata.
