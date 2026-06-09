# GitHub Publication Checklist

Use this page as the public-facing metadata kit for the repository.

## Repository Description

Short description:

```text
Linux control center and cautious firmware/Cura workflow for EasyThreeD K9 / ET4000+ 3D printers.
```

Longer one-line description:

```text
Little Hands is a Linux desktop control center for EasyThreeD K9 / ET4000+ printers: SD printing, USB upload, manual-zero start, guarded recovery, firmware support, Cura profile docs, and field diagnostics.
```

## Suggested Topics

```text
easythreed
easythreed-k9
et4000plus
3d-printer
marlin-firmware
cura
linux
raspberry-pi
ch340
sd-printing
reprap
tkinter
```

## Suggested Social Preview

Use `docs/screenshots/little-hands-main-window.png` for now. It shows the actual app rather than a marketing illustration.

## Release Strategy

Start with one conservative public baseline release:

- tag: `v0.1.0-public-baseline`
- title: `Little Hands v0.1.0 - K9 public baseline`
- release notes: [docs/releases/v0.1.0-public-baseline.md](releases/v0.1.0-public-baseline.md)

Keep `LH v5` as the recommended public firmware in the first release. Mention the `LH v6` controlled-hotbed build only as experimental.

## Checks / CI

Local checks are documented in `CONTRIBUTING.md`.

Do not add a live GitHub Actions workflow until the repository owner's GitHub Actions billing/account state is healthy. A first attempt at a smoke workflow failed before running any job because GitHub reported the account locked due to a billing issue; keeping that workflow would make the public project look broken even though the local checks pass.

## License Decision

No repository license is committed yet. For public reuse, choose one explicitly before broader promotion.

Recommended default if the project is meant to be permissive open source:

- `MIT` for app/docs helper code simplicity

Possible alternatives:

- `GPL-3.0-or-later` if derived firmware/source obligations should strongly shape downstream app changes
- `Apache-2.0` if explicit patent language is desired

Do not add a license accidentally; this is a maintainer decision.

## Public Post Tags

```text
EasyThreeD K9
EasyThreed K9
ET4000+
3D printing
Marlin
Cura
Linux
Raspberry Pi
CH340
SD printing
open source
```
