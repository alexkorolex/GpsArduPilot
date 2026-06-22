# ArduPlane 4.6.3: EKF3 navigation without GPS

This project contains a Plane-only patch and SITL configuration for an AUTO
mission without GPS. Flight remains on EKF3. In SITL, horizontal position and
velocity come directly from the simulator's NSU state without MAVLink
navigation messages. Height comes from the barometer, yaw from the compass,
and airspeed is used to make the wind states observable.

Pure IMU dead reckoning is deliberately not used. Low-cost inertial sensors
cannot provide a bounded global position without an external correction. This
matches the ArduPilot [Non-GPS Navigation](https://ardupilot.org/copter/docs/common-non-gps-navigation-landing-page.html)
guidance.

## Contents

- `ardupilot/` - ArduPilot Plane 4.6.3 source tree.
- `patches/ardupilot/plane-ekf3-inertial-gps.patch` - complete unified diff.
- `params/plane-sitl-nsu-no-gps.parm` - EKF3 no-GPS defaults.
- `PATCH_README.md` - architecture, setup, risks, and verification.
- `scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh` - apply/check/reverse.
- `scripts/build-ardupilot-plane-ekf3-inertial-gps.sh` - SITL build.

## EKF configuration

```text
AHRS_EKF_TYPE    3
EK2_ENABLE       0
EK3_ENABLE       1
EK3_SRC1_POSXY   6  # ExternalNav
EK3_SRC1_VELXY   6  # ExternalNav
EK3_SRC1_POSZ    1  # Barometer
EK3_SRC1_VELZ    6  # ExternalNav vertical velocity
EK3_SRC1_YAW     1  # Compass
VISO_TYPE        0
COMPASS_USE      1
ARSPD_USE        1
ARMING_CHECK     1
```

GPS drivers and SITL GPS sensors are disabled. `ARMING_CHECK=1` retains all
standard pre-arm checks; an unhealthy direct NSU solution must block arming.

## Required setup

For SITL, `--home` is the single geographic reference. Firmware sets EKF Origin
and Home from it internally, then feeds simulator position and velocity directly
to EKF3. No `SET_GPS_GLOBAL_ORIGIN`, `DO_SET_HOME`, VisualOdom or `sim:vicon`
transport is used.

QGroundControl still requires MAVLink for mission upload, arm/mode commands and
telemetry. That control channel is not a navigation measurement source.

## Patch and build

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --check
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh
```

The built SITL binary is `ardupilot/build/sitl/bin/arduplane`.

## Automated flight test

```sh
cd ardupilot
../venv/bin/python Tools/autotest/autotest.py \
  test.Plane.EKF3ExternalNavNoGPS --speedup=10
```

The test disables GPS, injects SITL ExternalNav, verifies the pre-arm failure
when that source is lost, verifies the QGC-like armable MANUAL startup, sets
matching Origin/Home, uploads the mission, takes off in AUTO, checks height and
wind estimation, verifies QGC's `GLOBAL_POSITION_INT.relative_alt`, flies the
circuit, lands, and disarms. The packaged `plane-elevrev` profile includes the
matching elevator/rudder reversals and QGC failsafe-Fact compatibility fields.
