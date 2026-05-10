# Установка На Linux / Raspberry Pi

Эта инструкция подходит для:

- Linux desktop
- Raspberry Pi OS Desktop
- других Debian-подобных систем, где есть `tkinter` и `pyserial`

## 1. Что Нужно

- Python `3`
- `tkinter`
- `pyserial`
- проигрывание звука для сигнала завершения печати
- доступ к USB serial-порту

## 2. Системные Пакеты

На Debian / Ubuntu / Raspberry Pi OS:

```bash
sudo apt update
sudo apt install -y \
  git \
  python3 \
  python3-tk \
  python3-serial \
  pulseaudio-utils
```

Опционально, но полезно:

```bash
sudo apt install -y python3-pil wmctrl gnome-screenshot
```

Пояснения:

- `python3-pil` текущему коду не обязателен, но это обычный полезный desktop-пакет
- `wmctrl` и `gnome-screenshot` нужны только для desktop-интеграции и скриншотов

## 3. Клонирование Репозитория

```bash
git clone <URL-ВАШЕГО-РЕПОЗИТОРИЯ>
cd littleHands
```

Если не хочется ставить `python3-serial` через apt, минимальный pip-вариант такой:

```bash
python3 -m pip install -r requirements.txt
```

## 4. Права На Serial-Порт

Добавь пользователя в группу `dialout`:

```bash
sudo usermod -aG dialout "$USER"
```

После этого нужно выйти из сессии и зайти снова.

## 5. Запуск Приложения

Из корня репозитория:

```bash
python3 tools/k9_control_center.py
```

Если всё в порядке, откроется окно `Little Hands`.

![Главное окно Little Hands](screenshots/little-hands-main-window.png)

## 6. Необязательный Desktop-Ярлык

В репозитории уже лежит:

- `Little Hands Control Center.desktop`

Чтобы установить ярлык локально:

```bash
mkdir -p ~/.local/share/applications
cp "Little Hands Control Center.desktop" ~/.local/share/applications/little-hands-control-center.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

## 7. Какие Файлы Создаёт Приложение

Little Hands пишет runtime-состояние и логи сюда:

- `monitor_logs/little_hands_runtime.log`
- `monitor_logs/little_hands_ui_state.json`
- `monitor_logs/gui_exports/`

Основной runtime-log — кольцевой, размером до `10 MiB`.

## 8. Cura Baseline

Используй:

- машина: `lilHands K9 warm mat`
- профиль: `codex - K9 warm mat cautious`
- текущий brim: `12 mm`
- температура PLA: `225C` первый слой, затем `224C`
- внешний тёплый стол: в Cura температура стола должна быть `0C`
- для `mainFlasherTop.STL`: supports everywhere, support interface / roof включены, support angle `35`

Не используй старые подрезанные пресеты машины из ранних экспериментов, если только не хочешь специально воспроизвести тот старый setup.

Кнопка `Экспорт профиля Cura` в приложении копирует текущий проверенный Cura bundle в `exports/`.
Для другой версии Cura / слайсера используй [cura/SETTINGS.ru.md](cura/SETTINGS.ru.md).

## 9. Особенности Raspberry Pi

На Raspberry Pi это приложение работает нормально, но:

- для капризного USB лучше powered hub
- во время прошивки лучше прямое USB-подключение к принтеру
- для полного сценария развёртывания на Raspberry Pi используй:
  - [../RASPBERRY_PI_CHECKLIST.md](../RASPBERRY_PI_CHECKLIST.md)

## 10. Если Приложение Не Запускается

Проверь по порядку:

1. `python3 --version`
2. `python3 -c "import tkinter"`
3. `python3 -c "import serial"`
4. `python3 tools/k9_control_center.py`

Если падает импорт `serial`, поставь `python3-serial` или:

```bash
python3 -m pip install -r requirements.txt
```

## 11. Если Принтер Не Находится

Этот проект заточен под `K9`, который обычно определяется как USB serial-устройство `CH340`.
`Little Hands` специально скрывает обычные не-принтерные serial-адаптеры вроде
`FTDI` и `/dev/ttyS*` из списка портов принтера. Это защита от случайной отправки
Marlin-команд в чужую serial-консоль.

Если принтер не находится:

- сделай power cycle принтера
- подключи USB напрямую
- заново открой `Little Hands`
- нажми `Find`

Если старт печати сорвался, принтер только щёлкает, не греется или телеметрия замёрзла, сейчас самый надёжный workflow такой:

1. `Hard stop`
2. power cycle принтера
3. заново проверить стартовую позу
4. `Save start`
5. стартовать печать снова

Если хотенд греется, принтер двигается или пластик уже идёт, не делай power cycle только из-за молчащей USB-телеметрии.
