#!/bin/bash
# E2E Test Runner Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "Running E2E Tests"
echo "========================================="

PASSED=0
FAILED=0
TOTAL=0

for i in {1..10}; do
    TEST_DIR="test_$i"
    PROMPT_FILE="test_${i}_prompt.txt"
    
    if [ ! -f "$PROMPT_FILE" ]; then
        echo "⚠️  Test $i: Prompt file not found: $PROMPT_FILE"
        continue
    fi
    
    TOTAL=$((TOTAL + 1))
    echo ""
    echo "----------------------------------------"
    echo "Test $i: $(head -n 1 "$PROMPT_FILE")"
    echo "----------------------------------------"
    
    # Ensure workspace directory exists
    mkdir -p "$TEST_DIR"
    
    # Run test
    if ATLOOP__RUNTIME__WORKSPACE_ROOT="./$TEST_DIR" ATLOOP__SANDBOX__LOCAL_TEST=true uv run atloopc exec-file "./$PROMPT_FILE" 2>&1 | tee "test_${i}_output.log"; then
        echo "✓ Test $i: PASSED"
        PASSED=$((PASSED + 1))
    else
        echo "❌ Test $i: FAILED"
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
done

echo "========================================="
echo "Test Summary"
echo "========================================="
echo "Total: $TOTAL"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "========================================="

if [ $FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi
