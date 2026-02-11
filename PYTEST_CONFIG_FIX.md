# Pytest Configuration Conflict Fix

## Problem Statement
Pytest was failing to start due to duplicate coverage arguments, preventing all Python tests from running in CI.

## Root Cause
The coverage argument `--cov=tinywindow` was specified in two places:

1. **pytest.ini** (permanent configuration):
```ini
[pytest]
addopts = 
    -v
    --tb=short
    --strict-markers
    --cov=tinywindow          # ← First occurrence
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=70
```

2. **CI Workflow** (.github/workflows/test.yml):
```yaml
- name: Run tests
  run: cd python-agent && pytest --cov=tinywindow --cov-report=xml
                                  ^^^^^^^^^^^^^^^^ Second occurrence (duplicate)
```

When pytest starts, it processes both the `addopts` from pytest.ini AND the command-line arguments, resulting in:
```
pytest --cov=tinywindow (from pytest.ini) --cov=tinywindow (from command) --cov-report=xml
```

This duplicate causes pytest to fail with a configuration conflict error before any tests can run.

## Solution
Remove the duplicate `--cov=tinywindow` argument from the CI workflow command, keeping only the additional report format needed for CI.

### Change Made

**File**: `.github/workflows/test.yml`  
**Line**: 89

**Before**:
```yaml
- name: Run tests
  run: cd python-agent && pytest --cov=tinywindow --cov-report=xml
```

**After**:
```yaml
- name: Run tests
  run: cd python-agent && pytest --cov-report=xml
```

## Technical Details

### Why This Works

1. **pytest.ini is always loaded**: Pytest automatically reads pytest.ini and applies all `addopts` settings
2. **Command-line supplements, not replaces**: Additional command-line arguments are merged with pytest.ini settings
3. **Duplicate --cov causes conflict**: Pytest doesn't allow the same coverage target to be specified multiple times
4. **--cov-report can be added**: Multiple report formats are allowed and get merged

### Final Effective Command

After the fix, when pytest runs in CI, it effectively executes:
```bash
pytest \
  -v \
  --tb=short \
  --strict-markers \
  --cov=tinywindow \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=xml \           # ← Added from command line
  --cov-fail-under=70
```

All the settings from pytest.ini are preserved, plus the XML report format needed for CI coverage uploads.

## Coverage Configuration

### Coverage Collection
- **Target**: `tinywindow` package
- **Threshold**: Minimum 70% coverage required
- **Fail on low coverage**: Yes (via `--cov-fail-under=70`)

### Coverage Reports Generated
1. **Terminal** (`--cov-report=term-missing`): Shows missing lines in console output
2. **HTML** (`--cov-report=html`): Generates htmlcov/ directory for local viewing
3. **XML** (`--cov-report=xml`): Generates coverage.xml for CI systems

## Impact

### Before Fix
- ❌ Pytest fails at startup with configuration conflict
- ❌ No tests run
- ❌ CI shows failure
- ❌ No coverage data collected

### After Fix
- ✅ Pytest starts successfully
- ✅ All tests run normally
- ✅ Coverage data collected
- ✅ All report formats generated
- ✅ CI can pass (if tests pass)

## Verification

To verify the fix works locally:

```bash
cd python-agent

# This should work now (no duplicate --cov=tinywindow)
pytest --cov-report=xml

# Coverage reports should be generated:
# - Terminal output with missing lines
# - htmlcov/index.html
# - coverage.xml
```

## Best Practices Learned

### Do ✅
- Keep common pytest settings in `pytest.ini`
- Use command line only for environment-specific settings (like extra report formats)
- Document what's in pytest.ini vs command line

### Don't ❌
- Duplicate arguments between pytest.ini and command line
- Specify the same `--cov` target multiple times
- Override pytest.ini settings without understanding the merge behavior

## Related Files

- `pytest.ini` - Main pytest configuration (permanent settings)
- `.github/workflows/test.yml` - CI workflow (environment-specific settings)
- `python-agent/tests/conftest.py` - Test fixtures and setup

## Additional Notes

### Why We Keep pytest.ini
- Provides consistent test configuration across all environments
- Developers and CI use the same settings
- Easier to maintain (one source of truth)

### Why We Add --cov-report=xml in CI
- XML format is required by many CI coverage tools (Codecov, Coveralls, etc.)
- Not needed for local development
- Doesn't conflict with other report formats

### Migration Path
If you need to change coverage settings:
1. Update `pytest.ini` for permanent changes
2. Only add to CI command if it's CI-specific
3. Test both locally and in CI

## Success Criteria

✅ Pytest starts without configuration errors  
✅ All tests can run  
✅ Coverage is collected correctly  
✅ All report formats are generated  
✅ CI tests pass (assuming tests themselves pass)  
✅ No duplicate arguments  

## Commit Details

- **Commit**: Fix pytest configuration conflict by removing duplicate --cov argument
- **Files Changed**: 1 file
- **Lines Changed**: 1 line (removed 17 characters)
- **Impact**: Fixes pytest startup, enables all Python tests to run

---

**Status**: ✅ FIXED  
**Type**: Configuration Error  
**Severity**: Critical (blocks all tests)  
**Resolution**: Remove duplicate argument  
