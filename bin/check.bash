#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

# Print functions
stdmsg() {
  local IFS=' '
  printf '%s\n' "$*"
}

errmsg() {
  stdmsg "$*" 1>&2
}

# Trap exit handler
trap_exit() {
  # It is critical that the first line capture the exit code. Nothing
  # else can come before this. The exit code recorded here comes from
  # the command that caused the script to exit.
  local exit_status="$?"

  if [[ ${exit_status} -ne 0 ]]; then
    errmsg 'The script did not complete successfully.'
    errmsg 'The exit code was '"${exit_status}"
  fi
}
trap trap_exit EXIT

base_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd -P)"
project_dir="$(cd "${base_dir}/.." >/dev/null && pwd -P)"

# cd to the directory before running rye
cd "${project_dir}"

# Check rye version (and whether it's installed or not)
# stdmsg "Checking if rye is installed..."
# version_string=$(rye --version | head -n 1 | cut -d ' ' -f 2)
# stdmsg "Rye version: ${version_string}"

stdmsg "Running rye sync..."
rye sync

stdmsg "Activating virtual environment..."
source .venv/bin/activate

stdmsg "Checking Python type hints with mypy..."
mypy

stdmsg "Running pylint..."
pylint src/ tests/

stdmsg "Checking import formatting with isort..."
isort src tests --check --diff

stdmsg "Checking Python code formatting with black..."
black --check --diff src tests

# Run shellcheck
# Recursively loop through all files and find all files with .sh extension and run shellcheck
stdmsg "Checking shell scripts with shellcheck..."
find . -type f \( -name "*.sh" -o -name "*.bash" \) -print0 | xargs -0 shellcheck --enable=all --external-sources

stdmsg "Checking shell script formatting with shfmt..."
shfmt --diff --simplify .

stdmsg "Running rye lint..."
rye lint

stdmsg "Running unit tests..."
coverage run -m pytest tests
coverage report -m
