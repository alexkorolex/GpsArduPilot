## ArduPilot helper для случайного GPS_INPUT

Этот проект — небольшой Python-слой вокруг ArduPilot SITL. Он выбирает GPS-точку, отправляет её в ArduPilot как `GPS_INPUT`, записывает MAVLink-трафик в JSONL и оставляет QGroundControl возможность напрямую загружать и запускать миссию.

Проект предназначен для экспериментов в SITL, а не для реальных аппаратов.

### Что было сделано

* `main.py` — тонкая обёртка для запуска команд.
* `external_gps/` содержит переиспользуемый код для GPS, MAVLink, логирования и CLI.
* `tests/` содержит unit-тесты, которые запускаются без SITL.

Провайдер по умолчанию — `random-simstate`. Он выбирает одну случайную стартовую точку рядом с `--static-lat/--static-lon`, затем читает ArduPilot `SIMSTATE` и переносит движение SITL на эту случайную точку перед отправкой `GPS_INPUT`. Этот режим нужно использовать, когда ты хочешь создать миссию в QGroundControl вокруг выбранной точки и заставить симулированный дрон пролететь её.

### Рабочий процесс SITL + QGroundControl

Терминал 1: запусти ArduCopter SITL и добавь MAVLink-выход для helper-скрипта:

```sh
cd ardupilot
Tools/autotest/sim_vehicle.py \
  -v ArduCopter \
  -f quad \
  --console \
  --map \
  --custom-location 55.0,37.0,180,0 \
  --out=udp:127.0.0.1:14560
```

Терминал 2: из корня проекта:

```sh
.venv/bin/python main.py \
  --connect udpin:0.0.0.0:14560 \
  --provider random-simstate \
  --static-lat 55.0 \
  --static-lon 37.0 \
  --static-alt 180 \
  --random-radius-max 300 \
  --random-seed 42 \
  --configure-sitl-gps-input \
  --set-home
```

Если `GPS1_TYPE` или `SIM_GPS1_ENABLE` изменились, перезапусти SITL один раз и запусти ту же команду снова с тем же `--random-seed`. Дождись, пока в консоли появится `Selected injected point`, а QGroundControl покажет аппарат рядом с этой координатой. После этого создай и загрузи миссию в QGroundControl вокруг этой точки и оставь helper-скрипт работать во время режима `AUTO`.

### Режимы провайдера

* `random-simstate`: рекомендуемый режим для тестов миссий QGroundControl в SITL.
* `random-point`: выбирает одну случайную точку и удерживает её; полезно для быстрой проверки GPS/EKF, но не для полёта по миссии.
* `static`: отправляет точные значения `--static-lat/--static-lon/--static-alt`.
* `demo-line`: двигается с фиксированной северной/восточной скоростью для простых локальных тестов.

### Проверка

Helper предупреждает, если ArduPilot сообщает позицию `GPS_RAW_INT`, которая находится слишком далеко от injected-точки. В таком случае убедись, что в SITL установлены `GPS1_TYPE=14` и `SIM_GPS1_ENABLE=0`, затем перезапусти SITL.

### Troubleshooting

`Got COMMAND_ACK: REQUEST_CAMERA_INFORMATION: UNSUPPORTED` — это QGroundControl запрашивает компонент камеры. Это не критично, если в этом тесте не нужна симулированная камера.

`Got COMMAND_ACK: REQUEST_MESSAGE: ACCEPTED` — это нормально.

`AP: EKF3 IMU0 is using GPS` и `AP: EKF3 IMU1 is using GPS` — хорошие признаки: EKF3 принял GPS-данные.

`AP: PreArm: Check mag field (z diff:1026>200)` означает, что магнитное поле компаса в ArduPilot не совпадает с моделью магнитного поля Земли для текущей GPS-локации. С этим helper-скриптом это обычно происходит, когда SITL стартует в дефолтной локации `CMAC`, а `GPS_INPUT` смещён в другую часть мира. Лучше запускать SITL с `--custom-location` рядом с теми же `--static-lat/--static-lon`, которые используются helper-скриптом. Для локальных SITL-экспериментов можно также передать `--disable-sitl-mag-field-check`, который выставляет `ARMING_MAGTHRESH=0`.

Запуск unit-тестов:

```sh
.venv/bin/python -m unittest discover -v
```
