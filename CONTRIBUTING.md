# Contributing

Rolemaker accepts focused bug fixes, usability improvements, documentation corrections, and tests for reproducible failure cases.

## Before starting

Check existing issues and pull requests. For a substantial feature or architectural change, open a feature request describing the problem and tradeoffs before implementing it. Keep changes small enough to review independently.

Follow the [README](README.md#native-development) for local setup and [testing guide](docs/testing.md) for validation. Integration and browser tests require isolated databases; never run destructive fixtures against application data.

## Bug reports

Use the bug-report template and include reproduction steps, expected behavior, actual behavior, and relevant environment details. Use synthetic documents when sharing a parsing or review issue. Remove credentials, contact information, session tokens, and personal document content from logs and screenshots.

## Pull requests

- Describe the concrete problem and resulting behavior.
- Preserve domain boundaries and existing authorization, transaction, and idempotency guarantees.
- Add regression coverage when fixing a behavioral defect. Explain which failure it exercises.
- Update affected API contracts, migrations, or documentation alongside the implementation.
- Run the checks appropriate to the change and report their results. Do not present mocked model responses as model-quality validation.

Use descriptive names based on responsibilities and behavior. Avoid unrelated refactoring and dependencies without a concrete need.

## Collaboration

Discuss the code and evidence respectfully. Explain disagreements, protect contributors' privacy, and avoid harassment or discriminatory language. Maintainers may close disruptive discussions or changes that do not fit the project's scope.

Contributions are submitted under the repository's [MIT license](LICENSE). Keep required third-party notices intact.
