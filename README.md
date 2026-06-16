## ArduPlane EKF3 Inertial GPS Patch

Этот проект хранит воспроизводимый patch для ArduPilot submodule. Patch добавляет в ArduPlane режим, в котором EKF3 не использует GPS-измерения и продолжает считать положение от EKF origin через инерциальное предсказание.

Решение предназначено для SITL-экспериментов и проверки Plane mission flow. Для реальных аппаратов изменение навигационной цепочки требует отдельного ревью.

### Что здесь лежит

* `ardupilot/` — ArduPilot как submodule.
* `patches/ardupilot/plane-ekf3-inertial-gps.patch` — source of truth для firmware patch.
* `scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh` — скрипт применения patch к submodule.
* `scripts/build-ardupilot-plane-ekf3-inertial-gps.sh` — применяет patch и собирает готовый ArduPlane artifact.
* `requirements.txt` — опциональные Python-зависимости для штатного ArduPilot tooling.

После применения patch внутри submodule появляется подробная документация:

```text
ardupilot/docs/plane-ekf3-inertial-gps.md
```

### Что делает patch

Patch меняет только Plane-ветку поведения:

* добавляет Plane-only параметр `EK3_PLN_GPS`;
* при `EK3_PLN_GPS=0` отключает чтение GPS data и GPS yaw внутри EKF3;
* не пишет GPS measurements в `storedGPS`;
* не использует raw GPS как fallback для `getLLH()`;
* разрешает Plane EKF3 bootstrap без GPS lock, если есть валидный home/origin;
* переводит EKF3 в inertial/dead-reckoning режим без GPS aiding.

### Применение

Собрать готовый SITL artifact одной командой:

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh
```

Скрипт сам применяет patch, запускает `./waf configure --board sitl`, затем `./waf plane`. Сборка идет в директорию `ardupilot/build/<board>`.

Для SITL готовый firmware artifact будет здесь:

```text
ardupilot/build/sitl/bin/arduplane
```

Для hardware board итоговые файлы будут здесь:

```text
ardupilot/build/<board>/bin/arduplane*
```

Опция `--output-dir` только копирует итоговые файлы в выбранную директорию; основной build output все равно остается внутри `ardupilot/build/<board>`.

SITL artifact нельзя запускать как `arduplane plane`: модель задается флагом. Прямой запуск из корня проекта:

```sh
ardupilot/build/sitl/bin/arduplane \
  -w \
  --model plane \
  --home 55.7522,37.6156,180,0
```

Для запуска с MAVProxy и UDP bridge на QGroundControl используй `sim_vehicle.py`, как показано ниже.

Собрать firmware и сразу запустить SITL с MAVProxy:

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh --run-sitl
```

Этот режим после сборки запускает:

```sh
cd ardupilot
./Tools/autotest/sim_vehicle.py \
  -N \
  -v ArduPlane \
  -f plane \
  -w \
  --custom-location=55.7522,37.6156,180,0
```

`-N` означает не пересобирать заново внутри `sim_vehicle.py`, а использовать уже собранный `ardupilot/build/sitl/bin/arduplane`.

MAVProxy при таком запуске:

* подключается к firmware через `tcp:127.0.0.1:5760`;
* открывает output для QGroundControl на UDP `127.0.0.1:14550`;
* подключает SITL control port `127.0.0.1:5501`.

Если зависимости ArduPilot tooling еще не установлены, можно использовать добавленный `requirements.txt`:

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh --install-python-deps
```

Для конкретного Python:

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh \
  --install-python-deps \
  --python /opt/homebrew/opt/python@3.14/bin/python3.14
```

Скопировать результат в отдельную директорию:

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh \
  --output-dir dist/plane-ekf3-inertial-gps
```

Собрать под другую board:

```sh
scripts/build-ardupilot-plane-ekf3-inertial-gps.sh --board CubeOrange
```

### Только patch

Проверить состояние patch:

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --check
```

Наложить patch на чистый или обновленный `ardupilot` submodule:

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh
```

Снять patch:

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --reverse
```

Apply-скрипт идемпотентный: если patch уже применен, повторный запуск не меняет файлы.

### Ручная сборка ArduPlane SITL

`waf` должен запускаться из директории `ardupilot`, потому что там лежит `wscript`:

```sh
cd ardupilot
```

Если ArduPilot tooling пишет `you need to install empy`, `No module named 'pexpect'` или `No such file or directory: 'mavproxy.py'`, установи штатные зависимости ArduPilot для того Python, которым запускаются `waf` и `sim_vehicle.py`.

Официальный macOS-вариант:

```sh
./Tools/environment_install/install-prereqs-mac.sh -y
```

Минимально для ошибки из лога:

```sh
python3 -m pip install empy==3.3.4 pexpect MAVProxy
python3 -c "import em, pexpect"
command -v mavproxy.py
```

Если работаешь не в активном `venv`, можно добавить `--user`. Тогда убедись, что каталог user scripts есть в `PATH`:

```sh
python3 -m pip install --user empy==3.3.4 pexpect MAVProxy
export PATH="$(python3 -m site --user-base)/bin:$PATH"
command -v mavproxy.py
```

Если `waf` в выводе показывает конкретный интерпретатор, например `/opt/homebrew/opt/python@3.14/bin/python3.14`, используй именно его вместо `python3`. В активном `venv` команда `python3 -m pip install ...` обычно ставит `mavproxy.py` сразу в `venv/bin`.

После этого:

```sh
./waf configure --board sitl
./waf plane
```

Запуск SITL выполняй из той же директории `ardupilot`:

```sh
./Tools/autotest/sim_vehicle.py \
  -N \
  -v ArduPlane \
  -f plane \
  -w \
  --custom-location=55.7522,37.6156,180,0
```

`-N` нужен, если firmware уже собрана через build-скрипт или `./waf plane`. Если хочешь, чтобы `sim_vehicle.py` сам пересобрал firmware перед запуском, убери `-N`.

Прямой запуск уже собранного SITL binary без MAVProxy:

```sh
./build/sitl/bin/arduplane \
  -w \
  --model plane \
  --home 55.7522,37.6156,180,0
```

Если остаешься в корне `GpsArduPilot`, используй путь с префиксом `ardupilot/`:

```sh
ardupilot/Tools/autotest/sim_vehicle.py \
  -N \
  -v ArduPlane \
  -f plane \
  -w \
  --custom-location=55.7522,37.6156,180,0
```

В многострочной команде после `\` не должно быть пробела.

Сам patch не добавляет Python-файлы и не требует отдельного окружения проекта.

Если нужен запуск только firmware без MAVProxy, добавь `--no-mavproxy` к `sim_vehicle.py`. В этом режиме автоматического UDP bridge на `127.0.0.1:14550` не будет.

QGroundControl подключается к SITL через UDP `127.0.0.1:14550`.

### Минимальная настройка

```text
param set AHRS_EKF_TYPE 3
param set EK3_ENABLE 1
param set EK3_PLN_GPS 0
reboot
```

Чтобы явно убрать GPS из EKF source set 0:

```text
param set EK3_SRC1_POSXY 0
param set EK3_SRC1_VELXY 0
param set EK3_SRC1_VELZ 0
param set EK3_SRC1_POSZ 1
param set EK3_SRC1_YAW 1
reboot
```

Здесь `POSXY/VELXY/VELZ=0` означает `None`, `POSZ=1` означает `Baro`, `YAW=1` означает `Compass`.

Вернуть штатное использование GPS в EKF3:

```text
param set EK3_PLN_GPS 1
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

Проверить, что параметр попал в собранный `arduplane`:

```sh
strings ardupilot/build/sitl/bin/arduplane | rg "PLN_GPS"
```

Быстрая проверка patch-состояния:

```sh
scripts/apply-ardupilot-plane-ekf3-inertial-gps.sh --check
```

Полное описание алгоритма, параметров и ограничений находится в `ardupilot/docs/plane-ekf3-inertial-gps.md`.
