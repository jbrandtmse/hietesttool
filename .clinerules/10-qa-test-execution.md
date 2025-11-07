# QA Test Execution Protocol

## Purpose

This rule mandates that all QA reviews MUST include actual test execution to verify implementation quality beyond static code analysis.

## Rule Definition

**MANDATORY TEST EXECUTION:** When conducting QA reviews (@qa persona), you MUST execute the test suite and report actual results. Static code analysis alone is insufficient for quality gate decisions.

## When This Rule Applies

This rule applies to ALL QA reviews, regardless of:
- Story complexity
- Perceived code quality
- Time constraints
- Confidence in implementation

## Required Test Execution Steps

### 1. Unit Test Execution

**Command:**
```bash
python -m pytest tests/unit/test_<module>.py -v
```

**What to Check:**
- All unit tests pass (X/X PASSED)
- No test failures or errors
- Coverage metrics if available
- Test execution time (watch for slow tests)

### 2. Integration Test Execution

**Command:**
```bash
python -m pytest tests/integration/test_<module>.py -v
```

**What to Check:**
- Pass/fail/skip counts
- Connection errors or timeouts
- Threading or concurrency issues
- Resource cleanup problems

### 3. Full Test Suite (Optional but Recommended)

**Command:**
```bash
python -m pytest tests/ -v
```

**Benefits:**
- Catches cross-module integration issues
- Verifies no regression in other areas
- Provides complete coverage picture

## Recording Test Results

### In QA Results Section

Always include actual test execution results:

```markdown
### Test Execution Results

**Unit Tests:**
- Command: `python -m pytest tests/unit/test_mock_server.py -v`
- Result: 29/29 PASSED ✅
- Coverage: app.py 72%, config.py 96%

**Integration Tests:**
- Command: `python -m pytest tests/integration/test_mock_server_startup.py -v`
- Result: 4/10 FAILED ⚠️, 3 PASSED, 3 SKIPPED
- Critical Issues: Signal handler threading bug (ValueError)
```

### In Quality Gate File

Update gate decision based on ACTUAL test results:

```yaml
gate: PASS | CONCERNS | FAIL  # Based on test execution, not assumptions
evidence:
  tests_reviewed: <actual count>
  unit_test_pass_rate: <X/Y>
  integration_test_pass_rate: <X/Y>
  test_failures: <list of failed tests>
```

## Gate Decision Rules Based on Test Results

### PASS
- All unit tests pass (100%)
- All integration tests pass (100%) OR skipped with valid reason
- Coverage meets story requirements (typically 80%+)
- No critical failures

### CONCERNS
- All unit tests pass BUT
- Some integration tests fail (non-critical) OR
- Coverage below target but acceptable OR
- Test warnings that should be addressed

### FAIL
- Any unit test failures OR
- Critical integration test failures OR
- Coverage significantly below target (<60%) OR
- Tests reveal blocking production issues

## Why This Rule Exists

**Lesson Learned from Story 2.1:**
- Initial code review showed "excellent quality"
- All coding standards met perfectly
- Static analysis suggested 95%+ coverage
- **BUT actual test execution revealed:**
  - 4/10 integration tests failed
  - Critical threading bug with signal handlers
  - Actual coverage was 61-72%, not 95%+

**The Issue:**
Code can look perfect on paper but fail in practice. Tests are the reality check.

## Exceptions

There are NO exceptions to this rule. Even if:
- "The code looks perfect"
- "It's a simple story"
- "Previous stories passed easily"
- "We're running behind schedule"

**Always run the tests.**

## Integration with Review Workflow

### Modified Review Process

1. **Read story and implementation** (as normal)
2. **Analyze code quality** (as normal)
3. **🔴 STOP: Execute tests** (NEW - MANDATORY)
4. **Adjust gate decision based on actual results** (NEW)
5. **Update QA Results with test execution evidence**
6. **Create gate file with test-informed decision**

### Task Progress Checklist

Include test execution in your task_progress:

```markdown
- [ ] Read story file
- [ ] Review implementation code
- [ ] Check coding standards compliance
- [ ] **Execute unit tests and record results** ← MANDATORY
- [ ] **Execute integration tests and record results** ← MANDATORY
- [ ] Analyze test failures (if any)
- [ ] Update QA Results section
- [ ] Create quality gate file
```

## Examples

### Example 1: Tests Reveal Issue (Story 2.1)

**Initial Assessment (Code Review Only):**
- Gate: PASS
- Quality Score: 100
- Recommendation: Ready for Done

**After Test Execution:**
- Gate: CONCERNS (downgraded)
- Quality Score: 70 (reduced)
- Recommendation: Changes Required
- Issues Found: Threading bug, 4 test failures

**Lesson:** Test execution prevented shipping broken code.

### Example 2: Tests Confirm Quality

**Code Review:**
- Code looks good
- Standards compliant
- Well documented

**Test Execution:**
- Unit: 45/45 PASSED ✅
- Integration: 12/12 PASSED ✅
- Coverage: 92%

**Result:** Gate: PASS with confidence (evidence-based)

## Tool Assistance

Use the `execute_command` tool during reviews:

```xml
<execute_command>
<command>python -m pytest tests/unit/test_module.py -v</command>
<requires_approval>false</requires_approval>
</execute_command>
```

Wait for results, analyze output, then proceed with gate decision.

## Enforcement

- Reviews submitted without test execution will be considered **incomplete**
- Gate decisions must reference actual test results
- "Assumed" or "estimated" test results are not acceptable
- QA Results section must show commands run and output observed

## Success Criteria

A QA review meets this rule when:
- ✅ Tests were actually executed (commands shown)
- ✅ Results are documented with pass/fail counts
- ✅ Gate decision reflects actual test outcomes
- ✅ Any test failures are analyzed and documented
- ✅ Coverage numbers are actual, not estimated

## Priority

This is a **HIGH PRIORITY** rule that takes precedence over time constraints. Quality gates based on untested code assumptions can lead to:
- Production bugs
- Technical debt
- Loss of confidence in QA process
- Wasted developer time fixing issues that testing would have caught

**Better to spend 2 minutes running tests than 2 hours debugging production issues.**
