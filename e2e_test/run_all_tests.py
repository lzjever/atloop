#!/usr/bin/env python3
"""Run all E2E tests and collect issues."""

import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

TEST_DIR = Path(__file__).parent
ATLOOP_DIR = TEST_DIR.parent


class TestResult:
    def __init__(self, test_num: int, prompt: str, success: bool, error: str = "", output: str = ""):
        self.test_num = test_num
        self.prompt = prompt
        self.success = success
        self.error = error
        self.output = output
        self.duration = 0.0


def run_test(test_num: int, timeout: int = 300) -> TestResult:
    """Run a single test."""
    test_dir = TEST_DIR / f"test_{test_num}"
    prompt_file = TEST_DIR / f"test_{test_num}_prompt.txt"

    if not prompt_file.exists():
        return TestResult(
            test_num,
            "N/A",
            False,
            f"Prompt file not found: {prompt_file}",
        )

    prompt = prompt_file.read_text().strip()

    # Ensure workspace exists
    test_dir.mkdir(exist_ok=True)

    # Run test
    import os
    env = os.environ.copy()
    env["ATLOOP__RUNTIME__WORKSPACE_ROOT"] = str(test_dir)
    env["ATLOOP__SANDBOX__LOCAL_TEST"] = "true"

    cmd = [
        "uv", "run", "atloopc", "exec-file", str(prompt_file),
    ]

    print(f"\n{'='*60}")
    print(f"Test {test_num}: {prompt[:50]}...")
    print(f"{'='*60}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=ATLOOP_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        duration = time.time() - start_time

        output = result.stdout + result.stderr
        success = result.returncode == 0

        # Check for common error patterns
        error_msg = ""
        if not success:
            # Extract error from output
            lines = output.split("\n")
            error_lines = [
                line for line in lines
                if any(keyword in line.lower() for keyword in [
                    "error", "exception", "traceback", "failed", "critical"
                ])
            ]
            error_msg = "\n".join(error_lines[-10:])  # Last 10 error lines

        test_result = TestResult(test_num, prompt, success, error_msg, output)
        test_result.duration = duration

        if success:
            print(f"✓ Test {test_num} PASSED ({duration:.1f}s)")
        else:
            print(f"❌ Test {test_num} FAILED ({duration:.1f}s)")
            if error_msg:
                print(f"Error: {error_msg[:200]}")

        return test_result

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"⏱️  Test {test_num} TIMEOUT ({duration:.1f}s)")
        return TestResult(
            test_num,
            prompt,
            False,
            f"Test timed out after {timeout}s",
        )
    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 Test {test_num} EXCEPTION: {e}")
        return TestResult(
            test_num,
            prompt,
            False,
            f"Exception: {str(e)}",
        )


def verify_test_result(test_num: int) -> Tuple[bool, str]:
    """Verify test result by checking expected outputs."""
    test_dir = TEST_DIR / f"test_{test_num}"

    # Test-specific verification
    if test_num == 1:
        # Check 1.txt contains "hi world"
        file_path = test_dir / "1.txt"
        if file_path.exists():
            content = file_path.read_text()
            if "hi world" in content:
                return True, "File contains expected content"
            return False, f"File content incorrect: {content[:50]}"
        return False, "File 1.txt not found"

    elif test_num == 2:
        # Check greeting.py exists and has greet function
        file_path = test_dir / "greeting.py"
        if file_path.exists():
            content = file_path.read_text()
            if "def greet" in content and "Hello" in content:
                return True, "greeting.py contains greet function"
            return False, "greeting.py missing expected content"
        return False, "greeting.py not found"

    elif test_num == 3:
        # Check main.py and utils.py exist
        main_file = test_dir / "main.py"
        utils_file = test_dir / "utils.py"
        if main_file.exists() and utils_file.exists():
            main_content = main_file.read_text()
            utils_content = utils_file.read_text()
            if "import" in main_content and "add" in utils_content:
                return True, "Both files exist with expected content"
            return False, "Files missing expected content"
        return False, "main.py or utils.py not found"

    # For other tests, just check if any files were created
    files = list(test_dir.glob("*"))
    files = [f for f in files if f.is_file() and f.name != ".gitkeep"]
    if files:
        return True, f"Found {len(files)} file(s)"
    return False, "No files created"


def main():
    """Run all tests."""
    print("="*60)
    print("E2E Test Suite")
    print("="*60)

    results: List[TestResult] = []

    # Run tests 1-10
    for i in range(1, 11):
        result = run_test(i, timeout=300)
        results.append(result)

        # Verify result
        if result.success:
            verified, msg = verify_test_result(i)
            if not verified:
                result.success = False
                result.error = f"Verification failed: {msg}"
                print(f"⚠️  Test {i} verification failed: {msg}")

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed
    total_time = sum(r.duration for r in results)

    print(f"Total: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total time: {total_time:.1f}s")
    print()

    # Show failures
    if failed > 0:
        print("Failed Tests:")
        for r in results:
            if not r.success:
                print(f"  Test {r.test_num}: {r.prompt[:50]}...")
                if r.error:
                    print(f"    Error: {r.error[:100]}")
        print()

    # Save detailed report
    report_file = TEST_DIR / "test_report.txt"
    with open(report_file, "w") as f:
        f.write("E2E Test Report\n")
        f.write("="*60 + "\n\n")
        for r in results:
            f.write(f"Test {r.test_num}: {'PASSED' if r.success else 'FAILED'}\n")
            f.write(f"  Prompt: {r.prompt}\n")
            f.write(f"  Duration: {r.duration:.1f}s\n")
            if r.error:
                f.write(f"  Error: {r.error}\n")
            f.write("\n")

    print(f"Detailed report saved to: {report_file}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
