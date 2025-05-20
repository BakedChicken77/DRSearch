# Frontend Testing

This document explains how to run the tests for the frontend portion of the project.

## Prerequisites

1. Install the project dependencies:

```bash
cd drsearch_frontend
yarn install
```

2. Ensure the codebase passes linting and formatting:

```bash
yarn lint
yarn format
```

## Running Tests

Jest and React Testing Library are used for testing. All test files live under `app/components/__tests__`.

To execute the test suite run:

```bash
yarn test
```

This will invoke Jest using the configuration defined in `jest.config.js`. The command runs the tests in a jsdom environment suitable for React components.

## Notes

The CI environment used by Codex may not include Jest dependencies by default. If `yarn test` fails due to missing packages, install them or update the setup script in your environment accordingly.
