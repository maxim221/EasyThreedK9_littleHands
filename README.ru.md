# Little Hands Для EasyThreeD K9

Little Hands — это Linux-приложение для управления очень конкретной конфигурацией 3D-принтера:

- принтер: `EasyThreeD K9`
- семейство плат: `ET4000+ / ET4000PLUS`
- текущая проверенная прошивка: `LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`
- базовый слайсер: `Cura 5.11`
- нагрев стола: внешний `hotbed / warm mat`, не подключённый электрически к плате принтера

Проект пока ещё сыроват, но уже реально работает и печатает.

- работает управление по USB и SD
- работает заливка прошивки
- работает manual-zero workflow
- работают логи
- работает экспорт Cura
- проверка G-code перед заливкой ловит опасные или явно битые файлы
- работает мониторинг температуры и прогресса печати

Что ещё сыровато:

- это не универсальный пакет “для любого K9”
- настоящего авто-home по концевикам пока нет
- после реального неудачного старта без нагрева и движения самый надёжный способ восстановления — power cycle принтера
- Windows-дистрибутив пока только запланирован
- в приложении есть переключение RU / EN / ZH, но часть шероховатостей UI ещё тестируется

## Скриншот

![Главное окно Little Hands](docs/screenshots/little-hands-main-window.png)

![Окно Files and Firmware](docs/screenshots/little-hands-files-firmware-window.png)

![Окно Manual](docs/screenshots/little-hands-manual-window.png)

## Версии Документации

- English:
  - [README.md](README.md)
  - [Linux setup](docs/INSTALL_LINUX.md)
  - [Printer and firmware guide](docs/PRINTER_AND_FIRMWARE.md)
- Русский:
  - [README.ru.md](README.ru.md)
  - [Установка на Linux / Raspberry Pi](docs/INSTALL_LINUX.ru.md)
  - [Принтер и прошивка](docs/PRINTER_AND_FIRMWARE.ru.md)
- 中文:
  - [README.zh.md](README.zh.md)
  - [Linux / Raspberry Pi 安装](docs/INSTALL_LINUX.zh.md)
  - [打印机与固件说明](docs/PRINTER_AND_FIRMWARE.zh.md)

## Какая Конфигурация Сейчас Поддерживается

Текущий публичный baseline — это проверенная конфигурация `EasyThreeD K9`:

- протестированный принтер: `EasyThreeD K9`
- протестированное семейство плат: `ET4000+ / ET4000PLUS`
- протестированная прошивка: `LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`
- протестированное приложение: `tools/k9_control_center.py`
- протестированная машина Cura: `lilHands K9 warm mat`
- протестированный профиль Cura: `codex - K9 warm mat cautious`

Важно:

- не считай, что это без проверки подойдёт к любому случайному `K9`
- разные экземпляры `K9` уже вели себя по-разному в ходе работы

Если нужно поднять всё это на Raspberry Pi:

- [RASPBERRY_PI_CHECKLIST.md](RASPBERRY_PI_CHECKLIST.md)

## Как Здесь Работает Home

Здесь **не** используется обычный Marlin-сценарий `G28` по концевикам.

Вместо этого Little Hands использует manual-zero workflow:

1. Пользователь ставит принтер в известную стартовую позу печати.
2. Нажимает `Save start`.
3. Приложение даёт принтеру `G92 X0 Y0 Z0`.
4. `Go to start` возвращает принтер в этот логический ноль в рамках чистой текущей сессии.

Это означает:

- это рабочая операторская схема, а не настоящее sensor-based home
- после неудачного старта печати надёжнее всего обычно:
  - сделать power cycle принтера
  - ещё раз проверить стартовую позу
  - снова нажать `Save start`
- если хотенд греется, принтер двигается или пластик уже идёт, не делай power cycle только из-за молчащей USB-телеметрии

## Внешний Warm Mat / Hotbed

Проверенный публичный baseline использует внешний `warm mat / hotbed`.

- он греется отдельным внешним питанием
- он **не** управляется прошивкой принтера
- для прошивки и приложения это по-прежнему “без подогреваемого стола”
- рабочий диапазон в тестах был около `40–50C`

Важно:

- не клади случайную штатную пластиковую накладку прямо на голый внешний нагреватель
- используй термостойкую поверхность печати
- в проверенном сетапе использовался штатный перфорированный гибкий коврик на тёплой поверхности

## Быстрый Старт

1. Поставь Linux-зависимости:
   - [docs/INSTALL_LINUX.ru.md](docs/INSTALL_LINUX.ru.md)
2. Прочитай инструкцию по принтеру и прошивке:
   - [docs/PRINTER_AND_FIRMWARE.ru.md](docs/PRINTER_AND_FIRMWARE.ru.md)
3. Запусти приложение:

```bash
python3 tools/k9_control_center.py
```

4. В Cura выбери:
   - машина: `lilHands K9 warm mat`
   - профиль: `codex - K9 warm mat cautious`
   - brim: `6 mm`
   - поддержки для `mainFlasherTop.STL`: everywhere, interface / roof включены, support angle `35`

Публичная зафиксированная копия Cura baseline лежит в [docs/cura/](docs/cura/).
Ручное описание настроек для других версий слайсера: [docs/cura/SETTINGS.ru.md](docs/cura/SETTINGS.ru.md).

## Какую Прошивку Использовать

Текущий публичный рекомендуемый baseline:

- [`firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin`](firmware/LH-v4-YZSwap-AutoFan45-FAN1-z600-e1040-mksLite.bin)

Исторические и экспериментальные прошивки тоже лежат в `firmware/`, но это не лучший старт для нового пользователя.

## Структура Репозитория

- `tools/`
  - GUI Little Hands, USB/SD helper-код и helper для slicing через Cura
- `firmware/`
  - текущая рекомендуемая прошивка и исторические сборки
- `docs/`
  - инструкции по установке и работе с принтером
- `RASPBERRY_PI_CHECKLIST.md`
  - пошаговый чек-лист для Raspberry Pi
- `PROJECT_LOG.md`
  - подробный инженерный журнал проекта

## Статус

Этот репозиторий пока не притворяется полностью полированным продуктом.

Честнее всего описать его так:

- реально используется
- проверен на живом `K9`
- ещё развивается
- уже достаточно рабочий, чтобы печатать
