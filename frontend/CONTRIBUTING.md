# Best Practices

## Linter

This project uses _Create React App_ ESLint configuration as a base. You won't
be able to commit files with linting errors, and if you do a `--force`
you'll break CI.

We also use [Markdownlint](https://github.com/DavidAnson/markdownlint) for
Markdown files.

If you are using **VS Code**, you should install ESLint and Markdownlint
extensions. Not only it will show you linting errors but also you can set it to
fix some of them on save. To do so, edit your `settings.json` config file and
add the following:

```json
    "eslint.autoFixOnSave": true,
    "eslint.alwaysShowStatus": true,
    "eslint.validate": [
      "javascript",
      "javascriptreact"
    ]
```

## Branches

- `main` is our main branch for nightly builds
- Try to not develop directly on `main` branch
- merges to `main` should be through `pull request` practice.

### Branch naming

- `poc/branch-name` for proof of concepts
- `feat/branch-name` for new features like, components, services,
validations, flows, etc.
- `test/branch-name` for unit/integration tests
- `fix/branch-name` for bugfixing code
- `hotfix/branch-name` for bugfixing in prod
- `docs/branch-name` for documentation

### Pull Requests

- Define a reviewer from the team.
- Close the branch after PR merge (except when it has the `WIP` prefix).
Otherwise this'll keep a ton unnecessary of UAT environments.
- Focus on one task at time
- Make atomic/little commits
- Push before leaving the office
- Be sure all of your tests passed

## Commits

We use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
specification. This will allow us to create automatized changelogs and semantic
versioning. Because of this, _you won't be able to commit messages that do not
follow this specification_.

```text
feat: added hat wobble
^--^  ^---------------^
|     |
|     +-> Summary in past simple tense.
|
+-------> Type: chore, docs, feat, fix, refactor, style, or test.
```

### Commit Types

- `feat`: (new feature for the user, not a new feature for build script)
- `fix`: (bug fix for the user, not a fix to a build script)
- `docs`: (changes to the documentation)
- `style`: (formatting, missing semicolons, etc; no production code change)
- `refactor`: (refactoring production code, eg. renaming a variable)
- `test`: (adding missing tests, refactoring tests; no production code change)
- `chore`: (updating grunt tasks etc; no production code change)

## Testing

We use **[Jest](https://jestjs.io/)** for testing and. Tests are automatically
run during the Validate stage of the CI Pipeline.

The pipeline enforces a 40% minimum coverage as an incentive to write tests.
It's strongly recommended that you raised this threshold over time.

Jest can be configured via [jest.config.js](jest.config.js).
