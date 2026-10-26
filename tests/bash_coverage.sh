#!/usr/bin/env bash
# BASH_ENV hook for tests only. Records source locations, never expanded commands.
[[ -d "${APDATIFIER_BASH_COVERAGE_DIR-}" ]] || return 0

declare -A __apdatifier_coverage_seen
__apdatifier_coverage_pid=""

__apdatifier_coverage_record() {
    local source="$1" line="$2"
    case "$source" in */contents/tools/sh/*) ;; *) return 0 ;; esac
    [[ "$source" == /* ]] || source="$PWD/$source"
    [[ -r "$source" ]] || return 0

    if [[ "$__apdatifier_coverage_pid" != "$BASHPID" ]]; then
        exec {__apdatifier_coverage_fd}>>"$APDATIFIER_BASH_COVERAGE_DIR/trace-$BASHPID"
        __apdatifier_coverage_pid="$BASHPID"
    fi
    if [[ -z "${__apdatifier_coverage_seen[$source]-}" ]]; then
        local contents
        contents=$(<"$source")
        printf 'S\0%s\0%s\0' "$source" "$contents" >&"$__apdatifier_coverage_fd"
        __apdatifier_coverage_seen[$source]=1
    fi
    printf 'L\0%s\0%s\0' "$source" "$line" >&"$__apdatifier_coverage_fd"
    return 0
}

set -o functrace
trap '__apdatifier_coverage_record "${BASH_SOURCE[0]}" "$LINENO"' DEBUG
