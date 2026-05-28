## ArduPlane EKF3 GPS Monkeypatch

Этот проект хранит воспроизводимый monkeypatch для ArduPilot submodule. Патч добавляет в ArduPlane режим подмены GPS-точки внутри `AP_NavEKF3`, чтобы QGroundControl мог строить и запускать mission вокруг заданной или случайной fake-точки.

Решение предназначено для SITL-экспериментов и проверки mission flow. Для реальных аппаратов его нужно отдельно ревьюить как изменение навигационной цепочки.

### Что здесь лежит

* `ardupilot/` — ArduPilot как submodule.
* `patches/ardupilot/plane-ekf3-gps-monkeypatch.patch` — source of truth для firmware monkeypatch.
* `scripts/apply-ardupilot-plane-ekf3-gps-monkeypatch.sh` — скрипт применения patch к submodule.

После применения patch внутри submodule появляется подробная документация:

```text
ardupilot/docs/plane-ekf3-gps-monkeypatch.md
```

### Что делает patch

Patch меняет только Plane-ветку поведения:

* добавляет Plane-only параметры `EK3_MP_*`;
* подменяет `Location` в `NavEKF3_core::readGpsData()` до установки EKF origin и GPS fusion;
* поддерживает fixed-точку и deterministic random-точку вокруг базовой координаты;
* не включает это поведение для Copter/Rover/Sub.

### Применение

Проверить состояние patch:

```sh
scripts/apply-ardupilot-plane-ekf3-gps-monkeypatch.sh --check
```

Наложить patch на чистый или обновленный `ardupilot` submodule:

```sh
scripts/apply-ardupilot-plane-ekf3-gps-monkeypatch.sh
```

Снять patch:

```sh
scripts/apply-ardupilot-plane-ekf3-gps-monkeypatch.sh --reverse
```

Скрипт идемпотентный: если patch уже применен, повторный запуск не меняет файлы.

### Сборка ArduPlane SITL

Из директории `ardupilot`:

```sh
./waf configure --board sitl
./waf plane
```

Запуск SITL:

```sh
Tools/autotest/sim_vehicle.py \
  -v ArduPlane \
  -f plane \
  -w \
  --custom-location=55.7522,37.6156,180,0
```

QGroundControl подключается к SITL через UDP `127.0.0.1:14550`.

### Минимальная настройка

Fixed-точка:

```text
param set AHRS_EKF_TYPE 3
param set EK3_ENABLE 1
param set SIM_GPS1_FIXTYPE 3

param set EK3_MP_TYPE 1
param set EK3_MP_LAT 55.7522
param set EK3_MP_LNG 37.6156
param set EK3_MP_ALT 180

reboot
```

Random-точка:

```text
param set AHRS_EKF_TYPE 3
param set EK3_ENABLE 1
param set SIM_GPS1_FIXTYPE 3

param set EK3_MP_TYPE 2
param set EK3_MP_LAT 55.7522
param set EK3_MP_LNG 37.6156
param set EK3_MP_ALT 180
param set EK3_MP_RAD_MIN 0
param set EK3_MP_RAD_MAX 300
param set EK3_MP_SEED 42

reboot
```

Отключить monkeypatch:

```text
param set EK3_MP_TYPE 0
reboot
```

### Mission в QGroundControl

Для первого теста лучше использовать простой маршрут без landing pattern:

```text
Takeoff 100 m
Waypoint 1, 300-500 m от старта
Waypoint 2, 300-500 m от WP1
RTL
```

Plane не может висеть на месте, поэтому слишком близкие точки, `LOITER` или landing sequence могут выглядеть как вращение вокруг точки.

### Проверка

Проверить, что параметры попали в собранный `arduplane`:

```sh
strings ardupilot/build/sitl/bin/arduplane | rg "MP_TYPE|MP_LAT|MP_LNG|MP_ALT|MP_RAD|MP_SEED"
```

Быстрая проверка patch-состояния:

```sh
scripts/apply-ardupilot-plane-ekf3-gps-monkeypatch.sh --check
```

Полное описание алгоритма, параметров, QGroundControl статусов и troubleshooting находится в `ardupilot/docs/plane-ekf3-gps-monkeypatch.md`.
