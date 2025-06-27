# DRSearch Backend Testing Scripts

This directory contains several scripts for testing the DRSearch backend with fake components. The scripts have been separated to reduce overhead and provide focused functionality.

## Scripts Overview

### 1. `demo_fake_components.py` - Component Demonstration
**Purpose**: Quick demonstration of fake components without running tests
**Usage**: 
```bash
cd drsearch_backend
poetry run python ../test_full_app/demo_fake_components.py
```

**What it does**:
- Shows how fake LLM generates deterministic responses
- Demonstrates embedding similarity calculations
- Tests document retrieval functionality
- Validates MultiQueryRetriever compatibility
- Minimal overhead, fast execution

**Use when**:
- Developing or debugging fake components
- Verifying component behavior
- Learning how the fake components work

### 2. `run_backend_e2e_tests.py` - Focused Test Execution
**Purpose**: Run actual end-to-end tests without demo overhead
**Usage**:
```bash
cd drsearch_backend
poetry run python ../test_full_app/run_backend_e2e_tests.py [options]
```

**Options**:
- `--simple-only`: Run only simplified component tests
- `--full-only`: Run only full backend API tests
- `--verbose`: Enable verbose output

**What it does**:
- Sets up complete test environment
- Runs simplified component tests (always work)
- Runs full backend API tests (may be skipped due to Pydantic issues)
- Provides clear pass/fail results
- Optimized for CI/CD integration

**Use when**:
- Running tests in CI/CD pipelines
- Validating changes without demo overhead
- Focused testing scenarios

### 3. `run_backend_e2e_demo.py` - Orchestrator (Legacy)
**Purpose**: Orchestrate both demo and tests with options
**Usage**:
```bash
cd drsearch_backend
poetry run python ../test_full_app/run_backend_e2e_demo.py [options]
```

**Options**:
- `--demo-only`: Run only the component demo
- `--with-demo`: Run demo followed by tests
- Default: Run tests only

**What it does**:
- Delegates to the appropriate specialized script
- Maintains backward compatibility
- Provides unified interface

**Use when**:
- You want the old behavior with `--with-demo`
- Need to run both demo and tests together
- Backward compatibility is required

## Recommended Usage

### For Development
```bash
# Quick component check
poetry run python ../test_full_app/demo_fake_components.py

# Run tests
poetry run python ../test_full_app/run_backend_e2e_tests.py
```

### For CI/CD
```bash
# Fast, focused testing
poetry run python ../test_full_app/run_backend_e2e_tests.py --simple-only
```

### For Troubleshooting
```bash
# First verify components work
poetry run python ../test_full_app/demo_fake_components.py

# Then run tests with verbose output
poetry run python ../test_full_app/run_backend_e2e_tests.py --verbose
```

## Benefits of Separation

1. **Reduced Overhead**: Tests run faster without demo output
2. **Clear Separation**: Demo and testing concerns are separated
3. **Focused Debugging**: Easy to isolate component vs. test issues
4. **CI/CD Friendly**: Clean test output without demo noise
5. **Flexibility**: Run exactly what you need when you need it

## Test Files Structure

```
test_full_app/backend/
├── fake_components.py           # Core fake component implementations
├── test_backend_e2e_simple.py  # Simplified component tests (always work)
└── test_backend_e2e_example.py # Full backend API tests (may be skipped)
```

The simplified tests validate that fake components work correctly, while the full tests attempt to integrate with the actual backend API (may be skipped due to Pydantic v1/v2 compatibility issues). 