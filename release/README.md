## ArduPlane SITL без GPS

В релизе лежит готовый бинарь SITL `arduplane` и файл параметров
`plane-sitl-nsu-no-gps.parm`.

Режим не использует кастомные EKF-параметры. GPS выключается штатными
параметрами ArduPilot, а коррекция борта ожидается от НСУ через EKF3
ExternalNav.

## Быстрый запуск

Откройте терминал в папке `release`:

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

`--model plane` обязателен: он выбирает симулятор самолета.

`--home` задает стартовую точку:

```text
широта,долгота,высота_м,курс_градусы
```

`-w` сбрасывает старые сохраненные параметры. Для первого запуска оставьте
`-w`, чтобы не подтянуть старый `eeprom.bin`.

## Подключение QGroundControl

MAVProxy не нужен.

Команда выше отправляет телеметрию напрямую в QGC по UDP
`127.0.0.1:14550`. Обычно QGC подключается автоматически.

Если UDP не подключился, можно запустить без `--serial0 ...` и в QGC создать
TCP-подключение к:

```text
127.0.0.1:5760
```

## Что делает файл параметров

GPS выключен:

```text
GPS1_TYPE      0
GPS2_TYPE      0
SIM_GPS_DISABLE  1
SIM_GPS2_DISABLE 1
SIM_GPS_TYPE   0
SIM_GPS2_TYPE  0
AHRS_GPS_USE   0
```

EKF3 включен и ждет коррекцию от НСУ:

```text
AHRS_EKF_TYPE  3
EK3_ENABLE     1
EK3_SRC1_POSXY 6
EK3_SRC1_VELXY 6
EK3_SRC1_POSZ  6
EK3_SRC1_VELZ  6
EK3_SRC1_YAW   1
VISO_TYPE      1
```

`6` означает `ExternalNav`, `1` для yaw означает `Compass`.
`VISO_TYPE=1` включает прием ExternalNav/VisualOdom данных от НСУ по MAVLink.

Pre-arm проверки не отключены. Если НСУ не отдает ExternalNav данные, arm
может не пройти, и это ожидаемо.

В файле также есть штатные Plane SITL значения RC и IMU-калибровки. Они нужны,
чтобы QGC не требовал ручной radio/accelerometer setup после каждого запуска с
`-w`. Это не отключение проверок.

## Логи

Логи включены в том же файле параметров. После запуска SITL пишет `.BIN` в:

```text
release/logs/
```

Получить читаемый текст после прогона:

```sh
../venv/bin/mavlogdump.py --types PARM,MSG,XKF0,XKF1,XKF2,XKF3,GPS,BARO,MAG logs/00000001.BIN > flight-readable.txt
```

## Остановка и файлы состояния

Остановить SITL можно через `Ctrl+C`.

При запуске в текущей папке появляется `eeprom.bin`; это нормально, там
хранятся параметры симулятора. Если нужно гарантированно стартовать с чистыми
параметрами, запускайте с `-w`.

## Частые проблемы

Если терминал пишет `permission denied`:

```sh
chmod +x ./arduplane
```

Если терминал пишет `bad CPU type in executable` или файл не запускается на
другой ОС, нужен отдельный бинарь под целевую платформу.

Если QGC не подключается по UDP, используйте TCP `127.0.0.1:5760`.
