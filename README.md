## ArduPlane SITL No-GPS / NSU ExternalNav

Пакет нужен для проверки ArduPlane SITL без GPS. В текущей версии патч не
добавляет кастомных EKF-параметров и не меняет EKF3-код: режим собирается
штатными параметрами ArduPilot.

Старый кастомный EKF-переключатель больше не используется и не должен
появляться ни в параметрах, ни в бинаре, ни в документации релиза.

### Что здесь лежит

* `ardupilot/` — ArduPilot как submodule.
* `patches/ardupilot/plane-ekf3-inertial-gps.patch` — source of truth для
  добавляемой документации и SITL defaults.
* `params/plane-sitl-nsu-no-gps.parm` — один список параметров для запуска
  SITL без GPS, с EKF3 ExternalNav-коррекцией от НСУ и onboard logs.
* `scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh` — применяет patch к
  submodule.
* `scripts/build-ardupilot-plane-ekf3-inertial-gps.sh` — применяет patch,
  собирает ArduPlane и при `--run-sitl` запускает сам `arduplane` напрямую.
* `release/` — готовый бинарь SITL и README для заказчика.

### Что делает конфигурация

* Полностью выключает GPS штатными параметрами: `GPS1_TYPE=0`,
  `GPS2_TYPE=0`, `SIM_GPS_DISABLE=1`, `SIM_GPS2_DISABLE=1`,
  `SIM_GPS_TYPE=0`, `SIM_GPS2_TYPE=0`, `AHRS_GPS_USE=0`.
* Включает EKF3: `AHRS_EKF_TYPE=3`, `EK3_ENABLE=1`.
* Настраивает основной EKF source set на НСУ/ExternalNav:
  `EK3_SRC1_POSXY=6`, `EK3_SRC1_VELXY=6`, `EK3_SRC1_POSZ=6`,
  `EK3_SRC1_VELZ=6`.
* Включает MAVLink backend для внешней одометрии НСУ: `VISO_TYPE=1`.
* Оставляет курс на компасе: `EK3_SRC1_YAW=1`.
* Добавляет штатные Plane SITL значения RC и IMU-калибровки, чтобы QGC не
  требовал ручной radio/accelerometer setup после каждого запуска с `-w`.
* Не обходит pre-arm проверки. Если НСУ не присылает ExternalNav данные,
  pre-arm/source checks должны ругаться, и это правильное поведение.
* Включает onboard DataFlash logs в file backend, чтобы параметры, pre-arm,
  EKF, BARO, MAG и другие сообщения попали в `.BIN` без MAVProxy.

### Важный ответ по корректировке

Борт должен корректироваться со стороны НСУ. Без GPS и без ExternalNav
коррекции длительный управляемый полет по координатам невозможен: EKF будет
только прогнозировать состояние по IMU и быстро накопит ошибку.

В этой конфигурации коррекция идет штатно через EKF3 ExternalNav sources.
Никакой отдельный MAVLink-скрипт, MAVProxy или программное отключение внутри
EKF не нужны.

### Быстрый запуск готового release

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

QGroundControl подключается напрямую к UDP `127.0.0.1:14550`. MAVProxy для
этой задачи не нужен.

Если QGC не слушает UDP, можно убрать `--serial0 ...` и подключиться из QGC
по TCP к `127.0.0.1:5760`.

### Сборка

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh
```

Готовый SITL binary:

```text
ardupilot/build/sitl/bin/arduplane
```

Собрать и сразу запустить SITL напрямую:

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh --run-sitl
```

Под другую board:

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh --board CubeOrange
```

### Только patch

Проверить состояние patch:

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --check
```

Наложить patch на чистый `ardupilot` submodule:

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh
```

Снять patch:

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --reverse
```

### Список параметров

Основной файл:

```text
params/plane-sitl-nsu-no-gps.parm
```

Ключевые значения:

```text
AHRS_EKF_TYPE    3
EK3_ENABLE       1
GPS1_TYPE        0
GPS2_TYPE        0
SIM_GPS_DISABLE  1
SIM_GPS2_DISABLE 1
SIM_GPS_TYPE     0
SIM_GPS2_TYPE    0
AHRS_GPS_USE     0
EK3_SRC1_POSXY   6
EK3_SRC1_VELXY   6
EK3_SRC1_POSZ    6
EK3_SRC1_VELZ    6
EK3_SRC1_YAW     1
VISO_TYPE        1
ARSPD_USE        1
RC1_MIN          1000
RC1_MAX          2000
RC1_TRIM         1500
RC3_MIN          1000
RC3_MAX          2000
RC3_TRIM         1000
INS_ACCOFFS_X    0.001
INS_ACCSCAL_X    1.001
INS_ACC2OFFS_X   0.001
INS_ACC2SCAL_X   1.001
INS_GYR_CAL      0
LOG_BACKEND_TYPE 1
LOG_BITMASK      65535
LOG_DISARMED     1
LOG_REPLAY       1
```

Значение `6` в `EK3_SRC1_*` — штатный `ExternalNav`. Значение `1` в
`EK3_SRC1_YAW` — штатный `Compass`.

### Логи

При запуске из `release/` `.BIN` появляется в:

```text
release/logs/
```

Сделать читаемый текст после запуска:

```sh
venv/bin/mavlogdump.py --types PARM,MSG,XKF0,XKF1,XKF2,XKF3,GPS,BARO,MAG logs/00000001.BIN > flight-readable.txt
```

Для релизного прогона я также сохраняю рядом текстовый лог, если SITL удается
запустить в текущем окружении.

### Проверка

Проверьте, что в параметрах и логах нет старого кастомного EKF-переключателя,
а активные значения совпадают с `plane-sitl-nsu-no-gps.parm`.
