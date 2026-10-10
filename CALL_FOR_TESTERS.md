# Call For EasyThreeD K9 / ET4000+ Testers

## RU: Нужны Тестеры EasyThreeD K9 / ET4000+

Little Hands уже работает на моём реальном EasyThreeD K9, но проекту нужны проверки на других экземплярах K9 / ET4000+.

Это Linux-приложение для локального управления маленьким K9: SD-печать, заливка G-code по USB, температура и явные разрывы телеметрии, журнал, ручной `manual-zero` старт, guarded recovery после штатного завершения, безопасное ручное восстановление после Stop, USB-метрики, прошивка и Cura-профиль.

Особенно полезны:

- фото платы и маркировки контроллера;
- какая версия K9 / ET4000+ у вас;
- Linux-дистрибутив и способ подключения по USB;
- успешно ли запускается `tools/k9_control_center.py`;
- видит ли приложение CH340 / ACM порт;
- отвечает ли принтер на `M115`, `M105`, `M27`;
- получается ли прочитать SD-файлы;
- любые отличия поведения после Stop, завершения печати или power cycle;
- после Stop проверяйте, что приложение не предлагает автоматический X/Y-возврат: старт восстанавливается только короткими наблюдаемыми jog и новым `Save start`;
- логи Little Hands / Marlin, если что-то пошло не так.

Важно: не прошивайте принтер и не запускайте движения, если не понимаете текущий workflow. У этого K9 нет надёжного классического home в текущей схеме; Little Hands использует manual-zero подход через `Save start`, а не обычный `G28`.

Репозиторий: https://github.com/maxim221/EasyThreedK9_littleHands

Контакт: https://t.me/NeuroMaxim

## EN: Looking For EasyThreeD K9 / ET4000+ Testers

Little Hands already works on my real EasyThreeD K9, but it needs testing on other K9 / ET4000+ units.

It is a Linux desktop control center for this small printer workflow: SD printing, USB G-code upload, temperature/status journal with explicit telemetry gaps, manual-zero start, guarded recovery after confirmed normal completion, safe manual restoration after Stop, USB metrics, firmware support, and Cura profile docs.

Useful feedback:

- controller board photos / markings;
- exact K9 / ET4000+ variant;
- Linux distro and USB connection details;
- whether `tools/k9_control_center.py` starts correctly;
- whether the app detects the CH340 / ACM printer port;
- whether the printer answers `M115`, `M105`, `M27`;
- whether SD file listing works;
- behavior differences after Stop, print completion, or power cycle;
- after Stop, verify that no automatic X/Y return is offered: restore start only with short watched jogs and a new `Save start`;
- Little Hands / Marlin logs when something fails.

Safety note: please do not flash firmware or run motion commands unless you understand the workflow. This K9 setup does not rely on normal endstop-based `G28`; Little Hands uses a manual-zero `Save start` model instead.

Project: https://github.com/maxim221/EasyThreedK9_littleHands

Contact: https://t.me/NeuroMaxim
