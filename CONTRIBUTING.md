# Contributing

Thanks for helping improve this project.

This repository uses a low-friction contribution model for v1:

- No contributor license agreement (CLA) is required.
- No developer certificate of origin (DCO) sign-off is required.
- Contributions are accepted under the repository license.

## Before You Start

- Search existing issues and pull requests before opening a new one.
- Keep pull requests focused on one change or tightly related set of changes.
- Do not use public issues or pull requests for security vulnerabilities. Follow [SECURITY.md](SECURITY.md) instead.

## Local Setup

1. Install the core prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), Docker, and [Task](https://taskfile.dev/).
2. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

3. Install dependencies for the workspace members you plan to touch:

   ```bash
   cd src/shared && uv sync
   cd ../api && uv sync --extra dev
   cd ../ingestion && uv sync --extra dev
   ```
4. Return to the repository root before running shared task commands.

Most contributor checks are local and public-safe. Running the API against live Bedrock is optional and may require your own AWS credentials, but the standard lint and test flow below does not.

## Recommended Checks

Run these before opening a pull request:

```bash
task lint
task test:unit
task local:test:integration:api
```

If you need to format code before committing:

```bash
task fmt
```

This checks the public-safe release gate: required files, banned/internal identifiers, secret patterns, and the fmt/lint/test commands used for publication readiness.

## Pull Request Expectations

- Explain what changed and why.
- Link the related issue when one exists.
- Include tests for bug fixes and new behavior when practical.
- Update docs in the same pull request when setup, configuration, behavior, or public interfaces change.
- Confirm you did not introduce secrets, internal-only references, or environment-specific values.

## Issue Guidelines

- Use the bug report form for reproducible defects.
- Use the feature request form for product or DX improvements.
- Use the question form for usage questions after checking the README and docs.

Include enough context for others to help quickly: your environment, the command or workflow you ran, what you expected, what happened instead, and any relevant logs or screenshots.

## Release and Governance Notes

- This project is maintained on a best-effort basis.
- There is no SLA, paid support path, or guaranteed response time in v1.
- Conduct expectations are defined in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
