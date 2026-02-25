#!/bin/bash
# Test execution script for BotSalinha
# Provides convenient interface for running different test suites

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
RUN_UNIT=false
RUN_INTEGRATION=false
RUN_E2E=false
RUN_ALL=false
PARALLEL=false
NO_COVERAGE=false
VERBOSE=false
FILTER=""

# Print usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Run BotSalinha test suites with various options.

OPTIONS:
    -u, --unit           Run unit tests only
    -i, --integration    Run integration tests only
    -e, --e2e            Run E2E tests only
    -a, --all            Run all tests (default if no suite specified)
    -p, --parallel       Run tests in parallel using pytest-xdist
    -n, --no-coverage    Disable coverage reporting
    -v, --verbose        Enable verbose output
    -f, --filter PATTERN Run only tests matching pattern
    -h, --help           Show this help message

EXAMPLES:
    # Run all tests
    $0 --all

    # Run unit tests only
    $0 --unit

    # Run all tests in parallel
    $0 --all --parallel

    # Run integration tests matching "database"
    $0 --integration --filter database

    # Run tests without coverage
    $0 --all --no-coverage

EOF
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--unit)
            RUN_UNIT=true
            shift
            ;;
        -i|--integration)
            RUN_INTEGRATION=true
            shift
            ;;
        -e|--e2e)
            RUN_E2E=true
            shift
            ;;
        -a|--all)
            RUN_ALL=true
            shift
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -n|--no-coverage)
            NO_COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -f|--filter)
            FILTER="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

# If no specific suite selected, run all
if [ "$RUN_UNIT" = false ] && [ "$RUN_INTEGRATION" = false ] && [ "$RUN_E2E" = false ]; then
    RUN_ALL=true
fi

# Build pytest command
PYTEST_CMD="uv run pytest"

# Add verbosity
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -vv"
else
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add coverage (unless disabled)
if [ "$NO_COVERAGE" = false ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src --cov-report=term-missing --cov-report=html"
fi

# Add parallel execution
if [ "$PARALLEL" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --numprocesses=auto --dist=loadfile"
fi

# Add filter if specified
if [ -n "$FILTER" ]; then
    PYTEST_CMD="$PYTEST_CMD -k $FILTER"
fi

# Determine which tests to run
TEST_PATHS=""
if [ "$RUN_ALL" = true ]; then
    TEST_PATHS="tests"
elif [ "$RUN_UNIT" = true ]; then
    TEST_PATHS="tests/unit"
    PYTEST_CMD="$PYTEST_CMD -m unit"
elif [ "$RUN_INTEGRATION" = true ]; then
    TEST_PATHS="tests/integration"
    PYTEST_CMD="$PYTEST_CMD -m integration"
elif [ "$RUN_E2E" = true ]; then
    TEST_PATHS="tests/e2e"
    PYTEST_CMD="$PYTEST_CMD -m e2e"
fi

# Set test environment variables
export BOTSALINHA_APP__ENV="testing"
export BOTSALINHA_DATABASE__URL="sqlite+aiosqlite:///:memory:"
export BOTSALINHA_DISCORD__TOKEN="test_token_for_ci"
export BOTSALINHA_GOOGLE__API_KEY="test_api_key_for_ci"

# Print banner
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  BotSalinha Test Runner${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Print configuration
echo -e "${YELLOW}Configuration:${NC}"
if [ "$RUN_ALL" = true ]; then
    echo -e "  Test Suite: ${GREEN}All Tests${NC}"
else
    if [ "$RUN_UNIT" = true ]; then
        echo -e "  Test Suite: ${GREEN}Unit Tests${NC}"
    fi
    if [ "$RUN_INTEGRATION" = true ]; then
        echo -e "  Test Suite: ${GREEN}Integration Tests${NC}"
    fi
    if [ "$RUN_E2E" = true ]; then
        echo -e "  Test Suite: ${GREEN}E2E Tests${NC}"
    fi
fi
echo -e "  Parallel: ${GREEN}${PARALLEL}${NC}"
echo -e "  Coverage: ${GREEN}${NO_COVERAGE=false}${NC}"
echo -e "  Verbose: ${GREEN}${VERBOSE}${NC}"
if [ -n "$FILTER" ]; then
    echo -e "  Filter: ${GREEN}${FILTER}${NC}"
fi
echo ""

# Print separator
echo -e "${BLUE}----------------------------------------${NC}"
echo ""

# Run tests
echo -e "${BLUE}Running:${NC} ${PYTEST_CMD} ${TEST_PATHS}"
echo ""

# Execute and capture exit code
if eval "$PYTEST_CMD $TEST_PATHS"; then
    EXIT_CODE=0
    STATUS="${GREEN}PASSED${NC}"
else
    EXIT_CODE=$?
    STATUS="${RED}FAILED${NC}"
fi

echo ""
echo -e "${BLUE}----------------------------------------${NC}"
echo -e "${BLUE}Result: ${STATUS}${NC}"

# Show coverage summary if coverage was enabled
if [ "$NO_COVERAGE" = false ] && [ -f "htmlcov/index.html" ]; then
    echo ""
    echo -e "${YELLOW}Coverage report: ${GREEN}htmlcov/index.html${NC}"
fi

exit $EXIT_CODE
