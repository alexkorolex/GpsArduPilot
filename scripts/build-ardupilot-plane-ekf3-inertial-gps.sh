#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Apply the Plane EKF3 inertial/no-GPS patch and build ArduPlane firmware.

Usage:
  scripts/build-ardupilot-plane-ekf3-inertial-gps.sh [options]

Options:
  --board BOARD              ArduPilot board to configure. Default: sitl.
  --output-dir PATH          Copy produced ArduPlane artifact(s) into PATH.
  --skip-patch               Do not apply/check the patch before building.
  --skip-configure           Do not run './waf configure'.
  --clean                    Run './waf clean' before building.
  --install-python-deps      Install Python tooling from requirements.txt first.
  --python CMD               Python command for --install-python-deps. Default: python3.
  --requirements PATH        Requirements file for --install-python-deps.
  --run-sitl                 Run SITL with MAVProxy after a successful build.
  --sitl-location LOCATION   SITL home as lat,lng,alt,heading. Default: 55.7522,37.6156,180,0.
  --no-wipe-eeprom           Do not pass -w to sim_vehicle.py when using --run-sitl.
  --mavproxy-args ARGS       Extra arguments passed to mavproxy.py through sim_vehicle.py.
  --ardupilot-dir PATH       Override the ArduPilot submodule path.
  --patch-file PATH          Override the patch file path.
  -h, --help                 Show this help.
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
    local root_dir="$1"
    local ardupilot_dir="$2"
    local patch_file="$3"
    local apply_script="$4"
    local requirements_file="$5"
    local install_python_deps="$6"
    local skip_patch="$7"

    [ -d "$ardupilot_dir/.git" ] || [ -f "$ardupilot_dir/.git" ] ||
        die "ArduPilot git worktree was not found: $ardupilot_dir"
    [ -x "$ardupilot_dir/waf" ] ||
        die "ArduPilot waf was not found or is not executable: $ardupilot_dir/waf"
    if [ "$skip_patch" = "false" ]; then
        [ -f "$patch_file" ] ||
            die "Patch file was not found: $patch_file"
        [ -f "$apply_script" ] ||
            die "Apply script was not found: $apply_script"
    fi
    [ -d "$root_dir" ] ||
        die "Project root was not found: $root_dir"

    if [ "$install_python_deps" = "true" ] && [ ! -f "$requirements_file" ]; then
        die "Requirements file was not found: $requirements_file"
    fi
}

install_python_requirements() {
    local python_cmd="$1"
    local requirements_file="$2"

    info "Installing ArduPilot Python tooling from: $requirements_file"
    "$python_cmd" -m pip install -r "$requirements_file"
}

apply_inertial_patch() {
    local apply_script="$1"
    local ardupilot_dir="$2"
    local patch_file="$3"

    bash "$apply_script" \
        --ardupilot-dir "$ardupilot_dir" \
        --patch-file "$patch_file"
}

configure_build() {
    local ardupilot_dir="$1"
    local board="$2"

    info "Configuring ArduPlane for board: $board"
    (
        cd "$ardupilot_dir"
        ./waf configure --board "$board"
    )
}

build_plane() {
    local ardupilot_dir="$1"
    local clean_build="$2"

    info "Building ArduPlane firmware"
    (
        cd "$ardupilot_dir"
        if [ "$clean_build" = "true" ]; then
            ./waf clean
        fi
        ./waf plane
    )
}

find_plane_artifacts() {
    local ardupilot_dir="$1"
    local board="$2"

    find "$ardupilot_dir/build/$board/bin" \
        -maxdepth 1 \
        -type f \
        -name 'arduplane*' \
        -print 2>/dev/null | sort
}

copy_artifacts() {
    local ardupilot_dir="$1"
    local board="$2"
    local output_dir="$3"
    local found="false"
    local artifact

    mkdir -p "$output_dir"

    while IFS= read -r artifact; do
        [ -n "$artifact" ] || continue
        cp "$artifact" "$output_dir/"
        found="true"
    done < <(find_plane_artifacts "$ardupilot_dir" "$board")

    [ "$found" = "true" ] ||
        die "No ArduPlane artifact was found in: $ardupilot_dir/build/$board/bin"

    info "Copied firmware artifact(s) to: $output_dir"
}

print_artifacts() {
    local ardupilot_dir="$1"
    local board="$2"
    local found="false"
    local artifact

    info "Firmware artifact(s):"

    while IFS= read -r artifact; do
        [ -n "$artifact" ] || continue
        printf '  %s\n' "$artifact"
        found="true"
    done < <(find_plane_artifacts "$ardupilot_dir" "$board")

    [ "$found" = "true" ] ||
        die "No ArduPlane artifact was found in: $ardupilot_dir/build/$board/bin"
}

print_sitl_run_hint() {
    local root_dir="$1"
    local board="$2"

    if [ "$board" != "sitl" ]; then
        return 0
    fi

    info "Run SITL artifact directly with:"
    printf '  %s/ardupilot/build/sitl/bin/arduplane -w --model plane --home 55.7522,37.6156,180,0\n' "$root_dir"
    info "Or use sim_vehicle.py when you want MAVProxy/QGroundControl bridge setup."
}

run_sitl_with_mavproxy() {
    local ardupilot_dir="$1"
    local sitl_location="$2"
    local wipe_eeprom="$3"
    local mavproxy_args="$4"
    local command=(
        ./Tools/autotest/sim_vehicle.py
        -N
        -v ArduPlane
        -f plane
        --custom-location "$sitl_location"
    )

    if [ "$wipe_eeprom" = "true" ]; then
        command+=(-w)
    fi

    if [ -n "$mavproxy_args" ]; then
        command+=(--mavproxy-args "$mavproxy_args")
    fi

    info "Starting SITL firmware with MAVProxy"
    info "QGroundControl UDP output: 127.0.0.1:14550"
    (
        cd "$ardupilot_dir"
        "${command[@]}"
    )
}

main() {
    local root_dir
    local ardupilot_dir
    local patch_file
    local apply_script
    local requirements_file
    local board="sitl"
    local output_dir=""
    local skip_patch="false"
    local skip_configure="false"
    local clean_build="false"
    local install_python_deps="false"
    local python_cmd="python3"
    local run_sitl="false"
    local sitl_location="55.7522,37.6156,180,0"
    local wipe_eeprom="true"
    local mavproxy_args=""

    root_dir="$(CDPATH= cd -- "$(script_dir)/.." && pwd)"
    ardupilot_dir="$root_dir/ardupilot"
    patch_file="$root_dir/patches/ardupilot/plane-ekf3-inertial-gps.patch"
    apply_script="$root_dir/scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh"
    requirements_file="$root_dir/requirements.txt"

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --board)
                [ "$#" -ge 2 ] || die "--board requires a value"
                board="$2"
                shift 2
                ;;
            --output-dir)
                [ "$#" -ge 2 ] || die "--output-dir requires a path"
                output_dir="$2"
                shift 2
                ;;
            --skip-patch)
                skip_patch="true"
                shift
                ;;
            --skip-configure)
                skip_configure="true"
                shift
                ;;
            --clean)
                clean_build="true"
                shift
                ;;
            --install-python-deps)
                install_python_deps="true"
                shift
                ;;
            --python)
                [ "$#" -ge 2 ] || die "--python requires a command"
                python_cmd="$2"
                shift 2
                ;;
            --requirements)
                [ "$#" -ge 2 ] || die "--requirements requires a path"
                requirements_file="$2"
                shift 2
                ;;
            --run-sitl)
                run_sitl="true"
                shift
                ;;
            --sitl-location)
                [ "$#" -ge 2 ] || die "--sitl-location requires a value"
                sitl_location="$2"
                shift 2
                ;;
            --no-wipe-eeprom)
                wipe_eeprom="false"
                shift
                ;;
            --mavproxy-args)
                [ "$#" -ge 2 ] || die "--mavproxy-args requires a value"
                mavproxy_args="$2"
                shift 2
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

    if [ "$run_sitl" = "true" ] && [ "$board" != "sitl" ]; then
        die "--run-sitl can only be used with --board sitl"
    fi

    check_paths "$root_dir" "$ardupilot_dir" "$patch_file" "$apply_script" "$requirements_file" "$install_python_deps" "$skip_patch"

    if [ "$install_python_deps" = "true" ]; then
        install_python_requirements "$python_cmd" "$requirements_file"
    fi

    if [ "$skip_patch" = "false" ]; then
        apply_inertial_patch "$apply_script" "$ardupilot_dir" "$patch_file"
    fi

    if [ "$skip_configure" = "false" ]; then
        configure_build "$ardupilot_dir" "$board"
    fi

    build_plane "$ardupilot_dir" "$clean_build"
    print_artifacts "$ardupilot_dir" "$board"
    print_sitl_run_hint "$root_dir" "$board"

    if [ -n "$output_dir" ]; then
        copy_artifacts "$ardupilot_dir" "$board" "$output_dir"
    fi

    if [ "$run_sitl" = "true" ]; then
        run_sitl_with_mavproxy "$ardupilot_dir" "$sitl_location" "$wipe_eeprom" "$mavproxy_args"
    fi
}

main "$@"
