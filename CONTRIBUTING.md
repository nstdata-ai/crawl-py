# Contributing

Keep existing package/import compatibility and trace endpoint changes against public backend controllers or official documentation.

Use Python 3.10+ in an isolated environment:

```sh
python -m pip install -e . build==1.6.1
python -m unittest discover -s tests -v
python -m build
python scripts/check-package.py dist
```

Use a fresh build output directory; package checks require exactly one wheel and one sdist. Keep version metadata, README installation commands and CHANGELOG aligned. To install a local build:

```sh
python -m pip install /PATH/TO/nstdata_ai_crawl-1.0.0-py3-none-any.whl
```

Package checks inspect the exact wheel and sdist, verify their contents and wheel RECORD hashes, and run the SDK regression suite outside the source tree. Release and packaging tool tests run in the source suite. The sdist includes both language guides, examples, tests and security reporting instructions.

The same check executes each README's pip command against a temporary local index in a fresh virtual environment, resolving the complete runtime dependency set and checking installed bytes, import origin and `pip check`. Runtime wheels are downloaded first; set `NSTDATA_PYTHON_WHEELHOUSE` to a prepared wheel directory for offline checks. These local checks do not prove public PyPI availability.

Update both READMEs and guides when public behavior changes. Tests execute the README and guide workflows through the real client with synthetic responses; the saved quick-start program also runs in a separate Python process against a loopback fixture. Package metadata converts repository-relative documentation links to absolute GitHub URLs for PyPI rendering. Request creation must remain single-attempt.

Tests must remain offline or loopback-only.

Do not record real credentials, provider bodies or billable targets.

Keep synchronous Requests limitations explicit; no creation retries, TLS bypass or raw network-error output.

A live check needs existing scope/budget authorization and separate evidence.

## Publishing

Use the manually dispatched `Publish PyPI` workflow from `main`, supplying the stable version and full reviewed commit SHA. It builds and checks one wheel/sdist pair, records their digests, then waits for approval in the `pypi-production` environment. The publish job verifies and uploads the same artifacts through PyPI Trusted Publishing; no persistent PyPI token is required.

Configure the GitHub environment with required reviewers, administrator bypass disabled and only the `main` branch allowed. The PyPI trusted publisher must match `nstdata-ai/crawl-py`, `release.yml` and `pypi-production`. A new project can use a [pending trusted publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

The official publishing action may retry individual HTTP 5xx uploads. If a run fails, inspect which files PyPI accepted before another dispatch; do not enable `skip-existing` or automatically rerun a partial release. After publication, the workflow compares both PyPI file digests and verifies a clean default installation. Publishing requires explicit authorization.
