# End-to-End Test Troubleshooting Guide

## Overview

This guide helps troubleshoot issues with the end-to-end tests, particularly when tests are being skipped unexpectedly.

## Current Test Status

Based on the analysis, there are **4 tests being skipped**:

1. **1 test from `e2e.spec.ts`**: Payload 3 is explicitly skipped with `test.skip`
2. **3 tests from `e2e_negative.spec.ts`**: Entire negative scenarios suite is skipped with `test.describe.skip`

## Verbose Logging Added

### Enhanced Test Runner (`run-e2e.mjs`)

The main test runner now includes verbose logging that shows:

- Environment variables and configuration
- Port allocation details
- Service startup progress
- Test execution details
- Coverage collection status

### Test Analysis Tool (`analyze-tests.mjs`)

Run this to analyze which tests are being skipped:

```bash
node test_full_app/analyze-tests.mjs
```

This will show:
- Which test files contain skipped tests
- Line numbers where tests are skipped
- Summary of total tests vs skipped tests
- Explanation of why tests are being skipped

### Test Toggle Tool (`toggle-skipped-tests.mjs`)

Easily enable/disable skipped tests for debugging:

```bash
# Enable all skipped tests
node test_full_app/toggle-skipped-tests.mjs enable

# Disable tests back to original state
node test_full_app/toggle-skipped-tests.mjs disable
```

## Running Tests with Verbose Output

To run the tests with maximum verbosity:

```bash
COLLECT_COVERAGE=1 node test_full_app/run-e2e.mjs
```

The enhanced logging will show:
- `[INFO]` messages for normal operations
- `[WARN]` messages for skipped tests
- `[ERROR]` messages for failures

## Specific Skip Reasons

### e2e.spec.ts - Payload 3 Skip

**Location**: Line 23
**Code**: `const t = idx === 2 ? test.skip : test;`
**Reason**: Payload 3 (index 2) is explicitly skipped

**To investigate**:
1. Check if payload3.json has any issues
2. Verify if trace3.sse is valid
3. Test if the skip is intentional or a bug

### e2e_negative.spec.ts - Negative Scenarios Skip

**Location**: Line 25
**Code**: `test.describe.skip("negative scenarios", () => {`
**Reason**: Entire negative scenarios suite is skipped

**To investigate**:
1. Check if the negative test scenarios are working
2. Verify if ERROR_500, SLOW_STREAM, and MALFORMED_SSE endpoints exist
3. Test if the skip is intentional or a bug

## Debugging Steps

1. **Analyze current state**:
   ```bash
   node test_full_app/analyze-tests.mjs
   ```

2. **Enable skipped tests temporarily**:
   ```bash
   node test_full_app/toggle-skipped-tests.mjs enable
   ```

3. **Run tests with verbose logging**:
   ```bash
   COLLECT_COVERAGE=1 node test_full_app/run-e2e.mjs
   ```

4. **Check logs**:
   - `test_full_app/logs/simulator1.out.log` - Backend simulator output
   - `test_full_app/logs/simulator1.err.log` - Backend simulator errors
   - `test_full_app/logs/frontend1.out.log` - Frontend server output
   - `test_full_app/logs/frontend1.err.log` - Frontend server errors

5. **Restore original state**:
   ```bash
   node test_full_app/toggle-skipped-tests.mjs disable
   ```

## Common Issues

### Tests Skipped Due to Intentional Configuration
- The current skips appear to be intentional for debugging purposes
- Check if these skips should be removed for production testing

### Environment Issues
- Verify `COLLECT_COVERAGE=1` is set correctly
- Check if all required services are running
- Ensure ports are available

### Test Data Issues
- Verify payload files exist and are valid JSON
- Check if trace files are accessible and valid
- Ensure test data matches expected format

## Next Steps

1. Investigate why payload 3 is being skipped in `e2e.spec.ts`
2. Determine if negative scenarios should be enabled in `e2e_negative.spec.ts`
3. Update test configuration based on findings
4. Consider adding more granular test controls for debugging 