# ArduPlane SITL: waypoint-миссия без GPS

Релиз содержит `arduplane` и `plane-sitl-nsu-no-gps.parm`.
Новых параметров нет. Используются штатные DCM, IMU, compass, barometer,
airspeed и Plane waypoint navigation.

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

QGroundControl подключается к UDP `127.0.0.1:14550`. Создайте миссию с
`Takeoff`, загрузите её, выберите `AUTO` и выполните arm.

Ожидаемые сообщения:

```text
SITL home used for DCM dead-reckoning
DCM: inertial position from Home
Triggered AUTO. Ground speed = ...
```

GPS fix и спутники должны оставаться нулевыми. MAVLink используется для
миссии и телеметрии QGC, но ExternalNav/VisualOdom/GPS_INPUT не используются.

Предупреждение: расчётная lat/lon дрейфует без абсолютной коррекции. Этот
бинарь предназначен для SITL и исследовательской проверки, не для безопасного
реального полёта.

Логи создаются в `release/logs/`. Остановка: `Ctrl+C`.
