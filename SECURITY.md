# Security And Safety Policy

Little Hands controls a physical 3D printer. Treat safety reports as both software and hardware reports.

## Supported Scope

The actively maintained public baseline is:

- EasyThreeD K9 / ET4000+ family
- Linux / Raspberry Pi desktop host
- Little Hands `tools/k9_control_center.py`
- `LH v5 ... Watch180` public firmware baseline
- Cura profile documented under `docs/cura/`

The `LH v6 ... Bed10K Max70` controlled-hotbed build is experimental and should be tested only under operator supervision.

## Report Privately When Needed

For issues that could cause unexpected motion, unsafe heating, or dangerous recovery behavior, contact:

- Telegram: https://t.me/NeuroMaxim

For ordinary bugs and compatibility reports, use GitHub Issues.

## Safety-Relevant Examples

- unexpected axis movement without an explicit operator action
- cold movement after a print start
- heater target lost while the app believes preheat is valid
- bed or hotend output staying on after an off command
- app recovery that could move into a printed part
- firmware or G-code validation allowing a known-dangerous command

Include logs and the exact command sequence whenever possible.
