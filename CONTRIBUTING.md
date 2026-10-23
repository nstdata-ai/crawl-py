# Contributing

Keep existing package/import compatibility and trace endpoint changes against public backend controllers or official documentation.

Use Python 3.10+ in an isolated environment:

```sh
python -m pip install -e . build
python -m unittest discover -s tests -v
python -m build
python scripts/check-package.py dist
```

Use a fresh build output directory; package checks require exactly one wheel and one sdist. Keep version metadata, README installation commands and CHANGELOG aligned. Before publication, install the approved local wheel instead of an older registry release:

```sh
python -m pip install /PATH/TO/nstdata_ai_crawl-1.0.0-py3-none-any.whl
```

Package checks install the wheel into an empty temporary target and run the full regression suite outside the source tree, verifying the import path. Runtime dependencies come from the current interpreter; this check does not resolve a new dependency set. The sdist includes both language guides, examples, tests and security reporting instructions.

Update both READMEs and guides when public behavior changes. Package checks verify their links and bilingual programs; tests execute the guide workflows through the real client with synthetic responses. Package metadata converts repository-relative documentation links to absolute GitHub URLs for PyPI rendering. Request creation must remain single-attempt.

Tests must remain offline or loopback-only.

Do not record real credentials, provider bodies or billable targets.

Keep synchronous Requests limitations explicit; no creation retries, TLS bypass or raw network-error output.

A live check needs existing scope/budget authorization and separate evidence; release requires explicit authorization.
