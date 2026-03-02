# Contributing to AymurAI

We are happy to accept contributions that help make `AymurAI` more useful, more robust, and easier to maintain.
To avoid unnecessary work on either side, please use the following flow.

## Contribution flow
1. Check whether there is already an issue for your topic: <https://github.com/AymurAI/backend/issues>
2. If not, open a new issue with context, motivation, and expected outcome.
3. Once the scope is clear, submit a pull request tied to that issue.

If you want to help and do not know where to start, small documentation fixes, test coverage improvements, and cleanup PRs are all welcome.

## Local development
If you want to get deeper into the API, we recommend cloning the repository and running the stack locally.
The codebase is fairly navigable, and most of the important modules are documented or organized by workflow.

### Option A: Docker (recommended)
You can use the provided compose services directly:

```bash
make api-up
# or make api-full-up
```

Swagger UI: `http://localhost:8899/docs`

If you prefer working from VS Code, the repository also includes a `.devcontainer/` setup.

### Option B: Local Python environment
Repository requires Python `3.10`.

```bash
# if using uv
uv sync --all-groups

# fallback with pip
pip install -e .
```

For most contributors, Docker is the easiest way to get a working API with the expected runtime dependencies.

## Pre-commit hooks
After installing dependencies, enable the hooks:

```bash
pre-commit install
```

Configured hooks currently include:
- `black`
- `nbstripout`

This helps keep code formatting consistent and prevents notebook output from leaking into commits.

## Formatting
If needed, you can run the formatter manually before committing:

```bash
black aymurai/
```

## Documentation policy
When behavior changes in API, pipelines, or DB persistence, update the corresponding docs in the same PR:
- `README.md`
- `docs/api/README.md`
- `docs/pipelines/README.md`
- `docs/pipelines/anonymizer/README.md`
- `docs/pipelines/datapublic/README.md`
- `docs/database/README.md`
- `docs/entities/README.md`
- `docs/models/README.md`

If the change is user-facing, documentation should land together with the code.

## Community and security
- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Security and ethics: [SECURITY.md](SECURITY.md)
