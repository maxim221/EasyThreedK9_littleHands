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
G1 Z10.0 F1800
G92 E0
```

## End G-code

Оси здесь raw Marlin, не операторские подписи UI. На проверенном K9 этот код поднимает голову и выдвигает стол к пользователю.

```gcode
M104 S0 ;Hotend off
M140 S0 ;Bed off in G-code even though bed is external
G91
G1 E-1 F1800
G1 Z10 F1200
G90
G1 X95 F3000
G1 Y95 F3000 ;Move bed toward the operator
```

Не добавляй в конец `M84`. Little Hands оставляет моторы доступными для послепечатного recovery workflow.

## Материал И Температура

- Материал: PLA
- Hotend первый слой: `218C`
- Hotend дальше: `214C`
- Температура стола в G-code: `0C`
- Реальный внешний warm mat / hotbed: вручную прогрет примерно до `40-50C`
- Обдув: `100%`
- Minimum layer time: `10 s`

## Качество

- Layer height: `0.16 mm`
- Initial layer height: `0.20 mm`
- Wall line count: `4`
- Top layers: `6`
- Bottom layers: `6`
- Infill density: `20%`
- Infill pattern: `lines`
- Print infill before walls: `off`
- Top / bottom pattern: `lines`
- Initial bottom pattern: `concentric`

## Скорости

- Print speed: `16 mm/s`
- Wall speed: `12 mm/s`
- Top / bottom speed: `12 mm/s`
- Infill speed: `18 mm/s`
- Travel speed: `40 mm/s`
- Initial layer speed: `7 mm/s`

## Адгезия

- Build plate adhesion: `brim`
- Brim width: `6 mm`

Не используй `10 mm` brim как default. Файл с `10 mm` brim выбирался на SD, но не входил в надёжный старт печати на проверенном K9.

## Поддержки

Для `mainFlasherTop.STL` и похожих деталей со сложными нависаниями:

- Generate support: `on`
- Support placement: `everywhere`
- Support overhang angle: `35 deg`
- Support structure: `normal`
- Support pattern: `zigzag`
- Support density: `12%`
- Support interface: `on`
- Support roof: `on`
- Support interface density: `85%`
- Support roof density: `85%`
- Support interface height: `0.8 mm`
- Support roof height: `0.8 mm`
- Support Z distance: `0.16 mm`
- Support top distance: `0.16 mm`
- Support XY distance: `0.2 mm`

Если preview не показывает поддержки под проблемной нижней поверхностью, не печатай. Меняй placement / threshold, пока support реально не появится в preview.

## Retract И Bridges

- Retraction: `on`
- Retraction distance: `6.5 mm`
- Retraction speed: `25 mm/s`
- Prime speed: `25 mm/s`
- Bridge settings: `on`
- Bridge fan speed: `100%`
- Bridge skin speed: `10 mm/s`
- Bridge wall speed: `10 mm/s`
- Bridge skin flow: `90%`
- Bridge wall flow: `90%`
- Initial layer line width: около `135%`

## Перед Записью На SD

Готовый G-code должен проходить этот чек-лист:

- нет настоящего стартового `G28`
- рядом со стартом есть `G92 X0 Y0 Z0`
- есть команда цели hotend, например `M104` / `M109`
- bed target остаётся `0C`
- bounds слайсера адекватные и укладываются в стол `100 x 100 mm`
- нет `Filament used: 0m`
- preview показывает поддержки там, где они нужны модели

Если что-то не сходится, переслайсь из настроек. Не правь G-code руками, если только специально не создаёшь новый файл и явно не маркируешь его как modified.
