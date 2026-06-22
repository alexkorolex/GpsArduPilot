# ArduPlane SITL: EKF3 mission without GPS

The release configuration keeps flight on EKF3 and replaces GPS horizontal
position/velocity with a direct in-process SITL NSU feed. Barometer, compass,
and airspeed remain enabled; all standard pre-arm checks remain active.

`--home` is used internally for both EKF Origin and Home. No external
VisualOdom stream, `sim:vicon`, `SERIAL5`, or MAVLink origin/home command is
required.

```sh
cd release
chmod +x ./arduplane
./arduplane \
  -w \
  --defaults plane-sitl-nsu-no-gps.parm \
  --model plane-elevrev \
  --speedup 1 \
  --home 55.7522,37.6156,180,0 \
  --serial0 udpclient:127.0.0.1:14550
```

QGroundControl uses UDP `127.0.0.1:14550` only for mission control and
telemetry. QGC itself cannot operate without MAVLink, but MAVLink is not used
as an EKF navigation or initialization source.

Expected status includes `EKF3 ... is using external nav data` and
`AHRS: EKF3 active`. `VISO_TYPE` remains `0`.

Use `plane-elevrev`, which is ArduPlane's default SITL frame. The plain `plane`
frame reverses the elevator response relative to the default ArduPlane servo
direction and can turn altitude feedback into a continuous climb. The packaged
defaults set `INITIAL_MODE=0` and `FLTMODE_CH=0`. Plane therefore waits in the
armable `MANUAL` mode while QGC has no mission, and the simulated RC channel
cannot replace a mode selected in QGC. Starting in `AUTO` without a loaded
mission makes Plane fall back to `RTL`; `RTL` is intentionally not armable.
`SIM_TERRAIN=0` provides a flat runway at Home, preventing the unbraked Plane
model from rolling down terrain while the mission is being prepared. The
`SERVO3_MIN/TRIM/MAX=1000/1000/2000` scale also makes disarmed throttle exactly
zero for the internal Plane model.
The packaged profile also applies the standard ArduPlane autotest elevator and
rudder reversals for `plane-elevrev`; without them AUTO demands nose-up while
the physical model pitches down and never leaves the runway.

Some QGC builds request the Copter/Rover facts `FS_OPTIONS`, `FS_GCS_TIMEOUT`,
and `FS_GCS_ENABLE` even for a fixed-wing vehicle. This SITL build exposes
read-only compatibility facts to prevent that dialog. Plane safety behavior
still uses `FS_GCS_ENABL` and `FS_LONG_TIMEOUT`.

In QGC, wait for `Ready To Fly`, create and upload the mission, select `AUTO`,
and then arm. The mission must begin with a fixed-wing takeoff command and end
with the landing pattern described below.

## QGC landing pattern

The defaults set `RTL_AUTOLAND=3`. QGC Fixed Wing Landing Pattern adds a
`DO_LAND_START` item; value `0` therefore blocks arming. Value `3` permits the
item for AUTO/go-around without making ordinary RTL enter the landing sequence.
Use `1` or `2` instead only when RTL should automatically select that sequence.

For a runway at the Home elevation with relative altitudes, use a touchdown
altitude of `0 m`. If the runway elevation differs from Home, use that elevation
difference instead. With a `40 m` height difference and a `5 deg` glide slope,
the required straight-line horizontal distance is about `457 m`.

See `../PATCH_README.md` for source configuration, Origin/Home handling, test
commands, and deployment risks.
