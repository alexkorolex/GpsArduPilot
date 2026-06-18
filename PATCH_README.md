# ArduPlane: waypoint-полёт без GPS и ExternalNav

Патч предназначен для экспериментальной проверки ArduPlane 4.6.3 в SITL.
Самолёт принимает waypoint-миссию из QGroundControl и выполняет её без GPS,
`GPS_INPUT`, ExternalNav и VisualOdom.

Новых параметров в firmware нет. Используются штатные DCM, airspeed, compass,
barometer, IMU, Plane navigation и MAVLink mission protocol.

## Что означает «без MAVLink»

MAVLink не используется как навигационный источник: в AHRS/EKF не поступают
внешние position/velocity/altitude/yaw measurements.

Для работы QGC MAVLink всё равно нужен как транспорт:

- загрузить waypoint-миссию;
- переключить режим и выполнить arm;
- показать телеметрию и расчётную позицию.

## Архитектура

Параметры выбирают штатный DCM:

```text
AHRS_EKF_TYPE 0
EK2_ENABLE    0
EK3_ENABLE    0
AHRS_GPS_USE  0
VISO_TYPE     0
ARSPD_USE     1
```

GPS полностью отключён:

```text
GPS1_TYPE        0
GPS2_TYPE        0
SIM_GPS_DISABLE  1
SIM_GPS2_DISABLE 1
SIM_GPS_TYPE     0
SIM_GPS2_TYPE    0
```

Горизонтальное перемещение DCM рассчитывает по штатной оценке скорости:
airspeed + attitude + compass yaw + wind estimate. Высотный канал Plane
остаётся на barometer/TECS.

Абсолютные широту и долготу получить из инерциальных датчиков невозможно,
поэтому один раз требуется начальная точка Home. В SITL она берётся из
`--home`. После старта новые координатные измерения не подмешиваются.

## Изменения кода

### `libraries/AP_AHRS/AP_AHRS_DCM.cpp`

Если сборка Plane, `AHRS_GPS_USE=0`, GPS отсутствует и Home уже задан, DCM
инициализирует dead-reckoning position из Home. Пока борт disarmed, позиция
заморожена, чтобы QGC не видел дрейф стоящего самолёта.

Риск: после arm ошибка compass, airspeed и wind estimate интегрируется прямо
в ошибку координат.

### `ArduPlane/ArduPlane.cpp`

Только в SITL при нулевом числе GPS-инстансов Home из `--home` один раз
передаётся в AHRS. На hardware этого SITL-пути нет: Home нужно задать штатной
командой GCS или другим существующим механизмом до arm.

### `ArduPlane/takeoff.cpp`

Штатный Plane запрещает AUTO takeoff без 3D GPS fix. Патч разрешает запуск
только при одновременно выполненных условиях:

- выбран `AHRS_EKF_TYPE=0`;
- зарегистрировано ровно `0` GPS-инстансов;
- Home задан;
- DCM выдаёт текущую Location.

Если GPS-инстанс существует, исходное требование 3D fix сохраняется.
Launch-speed берётся из штатного `ahrs.groundspeed()`.

## Параметры и pre-arm

Основной файл:

```text
params/plane-sitl-nsu-no-gps.parm
```

Новые AP_Param не добавлены. `ARMING_CHECK=2093046` сохраняет стандартные
проверки, кроме GPS и GPS configuration, которые заведомо отсутствуют.
Остальные проверки датчиков и конфигурации продолжают работать.

Параметры `TKOFF_THR_MINACC`, `TKOFF_THR_DELAY` и `TKOFF_THR_MINSPD`
по-прежнему управляют штатным AUTO launch-check. Для настоящего аппарата их
нужно настраивать под способ запуска; тестовые значения по умолчанию нельзя
слепо переносить на hardware.

## Запуск SITL и QGC

```sh
cd release
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

QGC подключается к UDP `127.0.0.1:14550`. Затем:

1. Создать миссию, где первый полётный item — `Takeoff`.
2. Добавить waypoint на разумном расстоянии.
3. Upload mission.
4. Переключить Plane в `AUTO`.
5. Выполнить arm.

## Ожидаемые сообщения

До arm:

```text
SITL home used for DCM dead-reckoning
DCM: inertial position from Home
```

После arm в AUTO:

```text
Triggered AUTO. Ground speed = ...
Takeoff complete at ...
Mission: ... WP
```

В QGC должно быть:

- GPS fix отсутствует, satellites = 0;
- карта показывает Home до arm;
- после arm расчётная позиция движется;
- `MISSION_CURRENT` переключается по item-ам;
- нет `PreArm: VisOdom not healthy`.

## Сборка

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh
```

Или напрямую:

```sh
cd ardupilot
./waf configure --board sitl
./waf plane
```

Бинарь:

```text
ardupilot/build/sitl/bin/arduplane
```

## Логи

Смотреть `MSG`, `MODE`, `CMD`, `NTUN`, `CTUN`, `BARO`, `MAG`, `ARSP`, `GPS`.
Ключевые проверки:

- `GPS` не содержит валидного fix;
- есть сообщения инициализации DCM от Home;
- `CTUN.ThO` становится ненулевым после `Triggered AUTO`;
- mission sequence переходит с Takeoff на WP;
- координата меняется, но её нельзя считать истинной без внешней коррекции.

## Проверенный SITL-сценарий

Проверка с Home `55.7522,37.6156,180,0` и миссией
`Home -> Takeoff 30 m -> waypoint ~111 m north` дала:

- arm result: accepted;
- `Triggered AUTO. Ground speed = 3.5`;
- throttle: до `100%`;
- `Takeoff complete at 31.20m`;
- mission sequence: `1 -> 2`;
- waypoint достигнут, после чего Plane перешёл в RTL;
- GPS fix оставался отсутствующим.

## Ограничения безопасности

Это не полноценная inertial navigation system и не production-решение.
Без GNSS/ExternalNav/оптической коррекции горизонтальная ошибка не ограничена.
Даже если QGC показывает красивую траекторию, фактическое положение реального
самолёта может быстро разойтись с картой.

Использовать сначала только в SITL. Перенос на hardware требует отдельного
анализа Home initialization, airspeed, compass, wind, geofence, RTL,
failsafe и безопасного launch procedure.

## Откат

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --reverse
```

Либо применить reverse к source-of-truth patch:

```sh
git -C ardupilot apply --reverse ../patches/ardupilot/plane-ekf3-inertial-gps.patch
```
