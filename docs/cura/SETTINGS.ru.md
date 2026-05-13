# Ручные Настройки Cura / Слайсера

Используй этот файл, если bundled Cura profile не импортируется или используется другая версия Cura / другой слайсер.

Это текущий проверенный baseline для EasyThreeD K9 / Little Hands. Настройки специально консервативные: медленная PLA-печать, внешний тёплый стол, manual-zero start, без управляемого firmware hotbed.

## Машина

- Название принтера: `lilHands K9 warm mat`
- Область печати: `100 x 100 x 100 mm`
- Origin at center: `off`
- Heated bed в прошивке: `off`
- G-code flavor: `RepRap (RepRap)` или ближайший Marlin / RepRap-style режим
- Диаметр филамента: `1.75 mm`
- Диаметр сопла: фактически установленное сопло; проверенный профиль Cura не переопределяет nozzle diameter

## Start G-code

Используй именно такой start G-code. Не добавляй `G28`.

```gcode
; Little Hands manual-zero workflow for EasyThreed K9 / K9 Plus
; Expected fixed start pose on this printer:
; X = fully left, Y = bed fully back (away from operator), Z = nozzle touching bed
; This pose is treated as logical 0,0,0. Do not G28 before print.
G92 X0 Y0 Z0
G1 Z10.0 F600
G92 E0
```

## End G-code

Оси здесь raw Marlin, не операторские подписи UI. На проверенном K9 этот код поднимает голову и выдвигает стол к пользователю.

```gcode
M204 P250 T120 ;Gentle final presentation moves for the small Y-bed
M104 S0 ;Hotend off
M140 S0 ;Bed off in G-code even though bed is external
G91
G1 E-1 F1800
G1 Z10 F1200
G90
G1 X95 F900
G1 Y95 F240 ;Move bed toward the operator
```

Не добавляй в конец `M84`. Little Hands оставляет моторы доступными для послепечатного recovery workflow.

## Материал И Температура

- Материал: PLA
- Hotend первый слой: `225C`
- Hotend дальше: `224C`
- Температура стола в G-code: `0C`
- Реальный внешний warm mat / hotbed: вручную прогрет примерно до `40-50C`
- Part-cooling в Cura: `off`
- Важно: у текущего K9 один физический вентилятор, он используется как firmware-managed hotend fan. Little Hands / helper удаляют slicer-команды `M106/M107`, чтобы Cura не управляла этим вентилятором как обдувом детали.
- Minimum layer time: `10 s`

## Качество

- Layer height: `0.16 mm`
- Initial layer height: `0.20 mm`
- Wall line count: `5`
- Top layers: `7`
- Bottom layers: `7`
- Infill density: `20%`
- Infill pattern: `lines`
- Print infill before walls: `off`
- Flow: `103%`
- Wall flow: `103%`
- Outer wall flow: `102%`
- Top / bottom flow: `104%`
- Infill flow: `101%`
- Initial layer flow: `103%`
- Skin overlap: `10%`
- Top / bottom pattern: `lines`
- Initial bottom pattern: `concentric`
- Ironing / выглаживание: `on`
- Iron only highest layer: `on`
- Ironing pattern: `concentric`
- Ironing line spacing: `0.12 mm`
- Ironing flow: `7%`
- Z seam alignment: `Random`

## Скорости

- Print speed: `15 mm/s`
- Wall speed: `12 mm/s`
- Top / bottom speed: `11 mm/s`
- Infill speed: `15 mm/s`
- Travel speed: `35 mm/s`
- Initial layer speed: `6 mm/s`
- Ironing speed: `8 mm/s`

## Сглаживание Движений

Эти лимиты специально мягкие для маленькой механики K9 и помогают уменьшить ringing / дребезг на диагональных перемещениях.

- Acceleration control: `on`
- Print acceleration: `250 mm/s^2`
- Wall acceleration: `180 mm/s^2`
- Outer wall acceleration: `150 mm/s^2`
- Inner wall acceleration: `200 mm/s^2`
- Top / bottom acceleration: `180 mm/s^2`
- Infill acceleration: `250 mm/s^2`
- Support acceleration: `220 mm/s^2`
- Support interface / roof acceleration: `160 mm/s^2`
- Initial layer and skirt / brim acceleration: `150 mm/s^2`
- Travel acceleration: `200 mm/s^2`
- Ironing acceleration: `120 mm/s^2`
- Jerk control: `off`
- Примечание: пока не включай Cura jerk control для этого RepRap-flavor профиля; наша Marlin-прошивка использует `M205`, а Cura в этом режиме генерирует `M566`.
- Ограничение сервисных движений K9: verified `LH-v4` сейчас хранит в EEPROM/Marlin `M201 X1000 Y1000` и `M204 T1000`, что слишком резко для ручных и recovery-движений маленькой механики. Для печати держи travel acceleration не выше `200 mm/s^2`; для длинных service/recovery-движений Little Hands оставляет мягкий service-idle режим `M204 T80` и ведёт стол примерно `F240`, для ручного jog стола использует `F300`, а голову влево/вправо ведёт примерно `F900`.

## Адгезия

- Build plate adhesion: `brim`
- Brim width: `14 mm`

Если снова отрывает углы, сначала проверь чистоту/прогрев стола и первый слой, затем можно временно поднять brim до `16 mm`. `18 mm` оставляем как аварийный вариант, потому что он заметно увеличивает площадь и время печати.

Для повторяемой трещины в одном углу используй физическую защитную стенку от сквозняка рядом с принтером. Не включай Cura Draft Shield по умолчанию: физическая стенка проще и не добавляет пластик в G-code.

## Поддержки

Для `mainFlasherTop.STL` и похожих деталей со сложными нависаниями:

- Generate support: `on`
- Support placement: `everywhere`
- Support overhang angle: `35 deg`
- Support structure: `normal`
- Support pattern: `zigzag`
- Support density: `10%`
- Support interface: `on`
- Support roof: `on`
- Support interface density: `65%`
- Support roof density: `65%`
- Support interface height: `0.48 mm`
- Support roof height: `0.48 mm`
- Support Z distance: `0.16 mm`
- Support top distance: `0.16 mm`
- Support XY distance: `0.3 mm`

Если поддержки держатся слишком крепко, сначала используй эти `easy-release` значения. Z-distance пока оставляем `0.16 mm`, чтобы не испортить нижнюю поверхность. Если снять поддержки всё ещё трудно, следующим отдельным тестом поднимай Support Z distance / top distance до `0.24-0.32 mm`.

Если preview не показывает поддержки под проблемной нижней поверхностью, не печатай. Меняй placement / threshold, пока support реально не появится в preview.

## Проверка Ориентации Модели

Для `moduleBot.STL` не печатай свежий slice, пока Cura Preview не подтверждает нужную ориентацию. Во время тестов 2026-05 прямой slice сырого `moduleBot.STL` дал перевёрнутый, support-heavy файл.

Практический sanity-check для этой модели: нормальная проверенная ориентация обычно даёт примерно `9-11 m` пластика. Если маленький `moduleBot` внезапно показывает около `20 m+` пластика или лес поддержек, не записывай файл на SD: проверь ориентацию в preview и переслайсь.

## Retract И Bridges

- Retraction: `on`
- Retraction distance: `6.5 mm`
- Retraction speed: `25 mm/s`
- Prime speed: `25 mm/s`
- Bridge settings: `on`
- Bridge fan speed: `0%`
- Bridge skin speed: `10 mm/s`
- Bridge wall speed: `10 mm/s`
- Bridge skin flow: `100%`
- Bridge wall flow: `100%`
- Initial layer line width: около `155%`

## Перед Записью На SD

Готовый G-code должен проходить этот чек-лист:

- нет настоящего стартового `G28`
- рядом со стартом есть `G92 X0 Y0 Z0`
- есть команда цели hotend, например `M104` / `M109`
- если файл загружается через Little Hands или slicing helper, ранний `M109` будет заменён на `M104`, а hotend прогреется перед SD-стартом
- bed target остаётся `0C`
- bounds слайсера адекватные и укладываются в стол `100 x 100 mm`
- высота укладывается в `100 mm`
- нет `Filament used: 0m`
- нет `M18/M84`, нагрева стола `M140/M190 S>0` и body `M204` выше безопасного K9 baseline
- preview показывает поддержки там, где они нужны модели

Если что-то не сходится, переслайсь из настроек. Не правь G-code руками, если только специально не создаёшь новый файл и явно не маркируешь его как modified.
