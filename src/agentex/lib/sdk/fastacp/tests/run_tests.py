#!/usr/bin/env python3
"""
Test runner for BaseACPServer and implementations.

This script provides various options for running the test suite:
- Run all tests
- Run specific test categories
- Run with different verbosity levels
- Generate coverage reports
- Run performance tests
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and return the result"""
    if description:
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'='*60}")

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run BaseACPServer tests")
    parser.add_argument(
        "--category",
        choices=["unit", "integration", "implementations", "error", "all"],
        default="all",
        help="Test category to run",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (use -v, -vv, or -vvv)",
    )
    parser.add_argument("--coverage", action="store_true", help="Run with coverage reporting")
    parser.add_argument(
        "--parallel", "-n", type=int, help="Run tests in parallel (number of workers)"
    )
    parser.add_argument(
        "--markers", "-m", help="Run tests with specific markers (e.g., 'not slow')"
    )
    parser.add_argument("--failfast", "-x", action="store_true", help="Stop on first failure")
    parser.add_argument(
        "--lf",
        "--last-failed",
        action="store_true",
        help="Run only tests that failed in the last run",
    )
    parser.add_argument(
        "--collect-only", action="store_true", help="Only collect tests, don't run them"
    )

    args = parser.parse_args()

    # Base pytest command
    cmd = ["python", "-m", "pytest"]

    # Add test files based on category
    test_files = {
        "unit": ["test_base_acp_server.py", "test_json_rpc_endpoints.py"],
        "integration": ["test_server_integration.py"],
        "implementations": ["test_implementations.py"],
        "error": ["test_error_handling.py"],
        "all": [
            "test_base_acp_server.py",
            "test_json_rpc_endpoints.py",
            "test_server_integration.py",
            "test_implementations.py",
            "test_error_handling.py",
        ],
    }

    # Add test files to command
    for test_file in test_files[args.category]:
        cmd.append(test_file)

    # Add verbosity
    if args.verbose:
        cmd.append("-" + "v" * min(args.verbose, 3))

    # Add coverage
    if args.coverage:
        cmd.extend(
            [
                "--cov=agentex.sdk.fastacp",
                "--cov-report=html",
                "--cov-report=term-missing",
                "--cov-branch",
            ]
        )

    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])

    # Add markers
    if args.markers:
        cmd.extend(["-m", args.markers])

    # Add fail fast
    if args.failfast:
        cmd.append("-x")

    # Add last failed
    if args.lf:
        cmd.append("--lf")

    # Add collect only
    if args.collect_only:
        cmd.append("--collect-only")

    # Add other useful options
    cmd.extend(
        [
            "--tb=short",  # Shorter traceback format
            "--strict-markers",  # Strict marker checking
            "--disable-warnings",  # Disable warnings for cleaner output
        ]
    )

    # Change to test directory
    test_dir = Path(__file__).parent
    original_cwd = Path.cwd()

    try:
        import os

        os.chdir(test_dir)

        # Run the tests
        success = run_command(cmd, f"Running {args.category} tests")

        if success:
            print(f"\n✅ All {args.category} tests passed!")
            if args.coverage:
                print("📊 Coverage report generated in htmlcov/")
        else:
            print(f"\n❌ Some {args.category} tests failed!")
            return 1

    finally:
        os.chdir(original_cwd)

    return 0


def run_quick_tests():
    """Run a quick subset of tests for development"""
    cmd = [
        "python",
        "-m",
        "pytest",
        "test_base_acp_server.py::TestBaseACPServerInitialization",
        "test_json_rpc_endpoints.py::TestJSONRPCMethodHandling",
        "-v",
        "--tb=short",
    ]

    return run_command(cmd, "Running quick development tests")


def run_smoke_tests():
    """Run smoke tests to verify basic functionality"""
    cmd = [
        "python",
        "-m",
        "pytest",
        "-m",
        "not slow",
        "-x",  # Stop on first failure
        "--tb=line",
        "test_base_acp_server.py::TestBaseACPServerInitialization::test_base_acp_server_init",
        "test_base_acp_server.py::TestHealthCheckEndpoint::test_health_check_endpoint",
        "test_json_rpc_endpoints.py::TestJSONRPCMethodHandling::test_message_received_method_routing",
    ]

    return run_command(cmd, "Running smoke tests")


def run_performance_tests():
    """Run performance-focused tests"""
    cmd = [
        "python",
        "-m",
        "pytest",
        "test_server_integration.py::TestServerPerformance",
        "test_error_handling.py::TestServerErrorHandling::test_server_handles_concurrent_errors",
        "-v",
        "--tb=short",
    ]

    return run_command(cmd, "Running performance tests")


if __name__ == "__main__":
    # Check if specific test type is requested via environment
    test_type = (
        sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ["quick", "smoke", "perf"] else None
    )

    if test_type == "quick":
        success = run_quick_tests()
    elif test_type == "smoke":
        success = run_smoke_tests()
    elif test_type == "perf":
        success = run_performance_tests()
    else:
        success = main()

    sys.exit(0 if success else 1)
