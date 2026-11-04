# Publishing to PyPI (one-time setup, by a maintainer with a PyPI account)

The publish workflow (`.github/workflows/publish.yml`) uses PyPI trusted publishing: GitHub proves to PyPI which
workflow is running, so no API token is created or stored.

1. Sign in at https://pypi.org (create an account with 2FA if needed).
2. Go to Your account > Publishing > "Add a new pending publisher".
3. Fill in: PyPI project name `prove-your-tests`; owner `quartercharts-com`; repository `prove-your-tests`;
   workflow name `publish.yml`; environment name `pypi`.
4. In this GitHub repository: Settings > Environments > New environment `pypi` (optionally require a reviewer).
5. Publish a GitHub Release (for example v0.1.0). The workflow builds and uploads; check
   https://pypi.org/project/prove-your-tests/ and then `pipx install prove-your-tests` in a clean shell.
