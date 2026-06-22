# ArduPlane: EKF3 AUTO flight without GPS

## Conclusion

The patch keeps `AHRS_EKF_TYPE=3` and `EK3_ENABLE=1`. GPS is replaced only as
the horizontal navigation source; EKF3 remains responsible for the flight
solution. In SITL, a Plane-only task directly feeds simulator NSU position and
velocity into EKF3. It does not use VisualOdom or MAVLink navigation messages.
IMU-only global navigation is not a supported fallback.

ArduPilot's [Non-GPS Navigation](https://ardupilot.org/copter/docs/common-non-gps-navigation-landing-page.html)
documentation likewise requires an alternative position/velocity source and an
EKF origin for modes that use global coordinates.

## Data flow

```text
SITL NSU position     -> writeExtNavData   -> EK3_SRC1_POSXY=6
SITL NSU velocity     -> writeExtNavVelData-> EK3_SRC1_VELXY/VELZ=6
Barometer             -> EK3_SRC1_POSZ=1  -> height
Compass               -> EK3_SRC1_YAW=1   -> heading
Airspeed + ground vel -> EKF3 wind states -> wind estimate / TECS inputs
```

`VISO_TYPE=0`. The Plane SITL scheduler reads `sitl_fdm` at 50 Hz and calls the
EKF API directly. `--home` initializes both Origin and Home inside firmware.
On real hardware this SITL-only feed does not exist; a production NSU still
requires its own native driver with consistent frames, timing, and covariance.

## Parameters

The source-of-truth defaults are in
`params/plane-sitl-nsu-no-gps.parm` and
`ardupilot/Tools/autotest/default_params/plane-sitl-nsu-no-gps.parm`.

```text
AHRS_EKF_TYPE     3
EK2_ENABLE        0
EK3_ENABLE        1
GPS1_TYPE         0
GPS2_TYPE         0
SIM_GPS_DISABLE   1
SIM_GPS2_DISABLE  1
AHRS_GPS_USE      0
EK3_SRC1_POSXY    6
EK3_SRC1_VELXY    6
EK3_SRC1_POSZ     1
EK3_SRC1_VELZ     6
EK3_SRC1_YAW      1
VISO_TYPE         0
COMPASS_USE       1
ARSPD_USE         1
ARMING_CHECK      1
RTL_AUTOLAND      3
INITIAL_MODE      0
FLTMODE_CH        0
SIM_TERRAIN       0
SERVO3_MIN        1000
SERVO3_TRIM       1000
SERVO3_MAX        2000
RC2_REVERSED      1
RC4_REVERSED      1
SERVO2_REVERSED   1
SERVO4_REVERSED   1
```

## Problems addressed

### Wind

The direct NSU feed supplies ground velocity while the airspeed sensor supplies air
velocity. EKF3 can therefore estimate wind instead of integrating a guessed
wind into a DCM position. The flight test applies a 4 m/s wind and checks the
reported speed and direction.

### Height

EKF3 uses barometric height (`EK3_SRC1_POSZ=1`) and direct NSU vertical velocity
(`EK3_SRC1_VELZ=6`). Plane/TECS therefore receives both a referenced height and
a measured climb rate instead of relying on uncorrected vertical prediction.

### Compass

Yaw explicitly uses the compass (`EK3_SRC1_YAW=1`), and `COMPASS_USE=1` keeps
its health and earth-field checks active. A magnetic-field warning immediately
after a simulated ground impact is a valid transient check failure; it clears
after the aircraft settles and must not be hidden by disabling compass checks.

### Pre-arm

`ARMING_CHECK=1` enables the complete standard check set. The test interrupts
the direct NSU feed and requires an AHRS pre-arm failure; arming proceeds only
after the source and EKF solution recover.

### Origin, Home, and altitude

Origin defines the geographic reference for local NSU coordinates. Home defines
relative mission altitude, RTL, and landing behavior. In SITL both are set from
the `--home LAT,LON,AMSL_ALT,HEADING` argument inside firmware. No MAVLink
origin/home command is sent.

### QGroundControl landing pattern

The defaults start in armable MANUAL (`INITIAL_MODE=0`) and disable RC mode
switch overrides (`FLTMODE_CH=0`). Starting in AUTO before QGC uploads a mission
would make Plane fall back to RTL, and RTL is intentionally not armable. Wait
for `Ready To Fly`, upload the complete mission, select AUTO, and then arm.
`SIM_TERRAIN=0` gives this dedicated test profile a flat runway at Home so the
simple Plane model does not roll down terrain while QGC is in Plan view. Its
throttle scale is explicitly `1000/1000/2000`, making disarmed output zero
instead of the 10% thrust produced by the stock 1100 us trim in this model.
The upstream `plane-elevrev` RC and servo reversals are included as well; this
keeps positive AUTO pitch demand physically nose-up.

Some QGC releases request Copter/Rover failsafe Facts before filtering the UI
for a fixed-wing vehicle. The SITL-only Plane parameter block supplies read-only
`FS_OPTIONS`, `FS_GCS_TIMEOUT`, and `FS_GCS_ENABLE` compatibility Facts. They
exist only to satisfy QGC and do not replace Plane's real failsafe parameters.

QGC adds `DO_LAND_START`, so `RTL_AUTOLAND=0` intentionally fails the Plane
mission pre-arm check. The packaged default is `3` (`OnlyForGoAround`): AUTO
can execute the landing sequence and go-around can return to its marker, while
ordinary RTL behavior is unchanged. Values `1` and `2` deliberately make RTL
enter the landing sequence.

The touchdown altitude is nominally `0 m` only for a runway at Home elevation
when mission altitudes are relative. Otherwise use `runway AMSL - Home AMSL`,
or use absolute AMSL altitudes consistently. Glide distance is
`height_difference / tan(glide_angle)`; `40 m` at `5 deg` is about `457 m`.

## Code changes

`libraries/AP_NavEKF3/AP_NavEKF3_core.cpp` allows Plane EKF3 bootstrap without
a 3D GPS fix only when ExternalNav is configured as the horizontal position
source. The estimator still waits for valid aiding data.

`ArduPlane/takeoff.cpp` accepts AUTO launch without GPS only when EKF reports a
healthy absolute horizontal position and velocity and is not in constant
position mode. Existing GPS installations retain the original 3D-fix rule.

`ArduPlane/sitl_nsu.cpp` is the Plane/SITL-only direct NSU backend. It is not
compiled into hardware firmware.

`ArduPlane/Parameters.cpp` exposes three SITL-only, read-only compatibility
Facts required by affected QGC versions. They are not connected to flight
failsafe decisions.

`Tools/autotest/arduplane.py` adds the complete takeoff-flight-land regression
test and its mission under `ArduPlane_Tests/EKF3ExternalNavNoGPS/`.

## Verification

```sh
cd ardupilot
../venv/bin/python ./waf plane
../venv/bin/python Tools/autotest/autotest.py \
  test.Plane.EKF3ExternalNavNoGPS --speedup=10
```

The test verifies all of the following in one scenario:

- EKF3 initializes from the direct NSU feed with both GPS instances disabled;
- `VISO_TYPE=0` and no `sim:vicon` transport is present;
- loss of the NSU feed causes a pre-arm failure;
- SITL waits in armable MANUAL before the mission is loaded;
- Origin and Home altitude agree;
- AUTO takeoff succeeds on a healthy EKF3 solution;
- barometric relative altitude is consistent with Home;
- `GLOBAL_POSITION_INT.relative_alt` reports the climb to QGC in millimeters;
- wind is estimated from ExternalNav velocity and airspeed;
- the aircraft completes the mission, lands, and disarms.

## Risks

This is not an IMU-only navigation mode. NSU loss, timestamp errors,
frame mismatch, scale error, or drift can move the EKF solution away from the
real aircraft. Hardware deployment still requires source-loss failsafes,
compass and airspeed calibration, vibration checks, geofence/RTL review, and
progressive flight testing after SITL.

## Patch operations

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --check
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --reverse
```
