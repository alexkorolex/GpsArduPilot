# ArduPlane 4.6.3: no-GPS waypoint SITL

Проект содержит экспериментальный Plane-only патч для выполнения
QGroundControl waypoint-миссии без GPS, ExternalNav и VisualOdom. Новые
параметры ArduPilot не добавляются.

DCM строит расчётную позицию от начального Home по штатным IMU, compass,
barometer, airspeed и wind estimate. MAVLink используется только для QGC,
mission protocol и телеметрии, но не как навигационный measurement input.

Важно: без абсолютной коррекции координатная ошибка не ограничена. Это режим
для SITL и исследований, не безопасная production-навигация.

## Состав

- `ardupilot/` — ArduPilot Plane 4.6.3.
- `patches/ardupilot/plane-ekf3-inertial-gps.patch` — полный unified diff.
- `params/plane-sitl-nsu-no-gps.parm` — SITL defaults без GPS.
- `PATCH_README.md` — архитектура, риски и проверка.
- `scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh` — apply/check/reverse.
- `scripts/build-ardupilot-plane-ekf3-inertial-gps.sh` — сборка.
- `release/` — готовый SITL binary и параметры.

Имя patch-файла сохранено для совместимости со скриптами; текущая реализация
не использует EKF3 и не ожидает НСУ/ExternalNav.

## Быстрый запуск

```sh
cd release
chmod +x ./arduplane
./arduplane \
  -w \
  --defaults plane-sitl-nsu-no-gps.parm \
  --model plane \
  --speedup 1 \
  --slave 0 \
  --sim-address=127.0.0.1 \
  -I0 \
  --home 55.7522,37.6156,180,0 \
  --serial0 udpclient:127.0.0.1:14550
```

QGC подключается к UDP `127.0.0.1:14550`. Загрузите миссию с `Takeoff`,
переведите Plane в `AUTO` и выполните arm.

## Ключевые штатные параметры

```text
AHRS_EKF_TYPE    0
EK2_ENABLE       0
EK3_ENABLE       0
GPS1_TYPE        0
GPS2_TYPE        0
SIM_GPS_DISABLE  1
SIM_GPS2_DISABLE 1
SIM_GPS_TYPE     0
SIM_GPS2_TYPE    0
AHRS_GPS_USE     0
VISO_TYPE        0
ARSPD_USE        1
ARMING_CHECK     2093046
```

## Patch

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --check
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --reverse
```

## Сборка

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh
```

Готовый binary:

```text
ardupilot/build/sitl/bin/arduplane
```

Подробности и проверенный mission-сценарий: `PATCH_README.md`.
