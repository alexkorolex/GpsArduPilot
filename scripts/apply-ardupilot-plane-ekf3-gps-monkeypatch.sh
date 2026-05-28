#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Apply the Plane EKF3 GPS monkeypatch to the local ArduPilot submodule.

Usage:
  scripts/apply-ardupilot-plane-ekf3-gps-monkeypatch.sh [options]

Options:
  --check                 Check whether the patch can be applied or is already applied.
  --reverse               Remove the patch from the ArduPilot submodule.
  --ardupilot-dir PATH    Override the ArduPilot submodule path.
  --patch-file PATH       Override the patch file path.
  -h, --help              Show this help.
USAGE
}

die() {
    printf 'error: %s\n' "$1" >&2
    exit 1
}

info() {
    printf '%s\n' "$1"
}

script_dir() {
    local source_dir
    source_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    printf '%s\n' "$source_dir"
}

check_paths() {
    local ardupilot_dir="$1"
    local patch_file="$2"

    [ -d "$ardupilot_dir/.git" ] || [ -f "$ardupilot_dir/.git" ] ||
        die "ArduPilot git worktree was not found: $ardupilot_dir"
    [ -f "$patch_file" ] ||
        die "Patch file was not found: $patch_file"
}

can_apply_patch() {
    local ardupilot_dir="$1"
    local patch_file="$2"

    git -C "$ardupilot_dir" apply --check "$patch_file" >/dev/null 2>&1
}

can_reverse_patch() {
    local ardupilot_dir="$1"
    local patch_file="$2"

    git -C "$ardupilot_dir" apply --reverse --check "$patch_file" >/dev/null 2>&1
}

check_patch_state() {
    local ardupilot_dir="$1"
    local patch_file="$2"

    if can_apply_patch "$ardupilot_dir" "$patch_file"; then
        info "Patch can be applied to: $ardupilot_dir"
        return 0
    fi

    if can_reverse_patch "$ardupilot_dir" "$patch_file"; then
        info "Patch is already applied in: $ardupilot_dir"
        return 0
    fi

    die "Patch does not apply cleanly. Check local ArduPilot changes or refresh the patch."
}

apply_patch_file() {
    local ardupilot_dir="$1"
    local patch_file="$2"

    if can_apply_patch "$ardupilot_dir" "$patch_file"; then
        git -C "$ardupilot_dir" apply "$patch_file"
        info "Patch applied to: $ardupilot_dir"
        return 0
    fi

    if can_reverse_patch "$ardupilot_dir" "$patch_file"; then
        info "Patch is already applied in: $ardupilot_dir"
        return 0
    fi

    die "Patch does not apply cleanly. Check local ArduPilot changes or refresh the patch."
}

reverse_patch_file() {
    local ardupilot_dir="$1"
    local patch_file="$2"

    if can_reverse_patch "$ardupilot_dir" "$patch_file"; then
        git -C "$ardupilot_dir" apply --reverse "$patch_file"
        info "Patch removed from: $ardupilot_dir"
        return 0
    fi

    if can_apply_patch "$ardupilot_dir" "$patch_file"; then
        info "Patch is not applied in: $ardupilot_dir"
        return 0
    fi

    die "Patch state is ambiguous. Check local ArduPilot changes manually."
}

main() {
    local root_dir
    local ardupilot_dir
    local patch_file
    local mode="apply"

    root_dir="$(CDPATH= cd -- "$(script_dir)/.." && pwd)"
    ardupilot_dir="$root_dir/ardupilot"
    patch_file="$root_dir/patches/ardupilot/plane-ekf3-gps-monkeypatch.patch"

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --check)
                mode="check"
                shift
                ;;
            --reverse)
                mode="reverse"
                shift
                ;;
            --ardupilot-dir)
                [ "$#" -ge 2 ] || die "--ardupilot-dir requires a path"
                ardupilot_dir="$2"
                shift 2
                ;;
            --patch-file)
                [ "$#" -ge 2 ] || die "--patch-file requires a path"
                patch_file="$2"
                shift 2
                ;;
            -h|--help)
                usage
                return 0
                ;;
            *)
                die "unknown option: $1"
                ;;
        esac
    done

    check_paths "$ardupilot_dir" "$patch_file"

    case "$mode" in
        check)
            check_patch_state "$ardupilot_dir" "$patch_file"
            ;;
        apply)
            apply_patch_file "$ardupilot_dir" "$patch_file"
            ;;
        reverse)
            reverse_patch_file "$ardupilot_dir" "$patch_file"
            ;;
    esac
}

main "$@"
