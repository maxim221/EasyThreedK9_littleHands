# Little Hands firmware protocol

Status: experimental `LH1`; installed and serial-validated in `LH v10 EXP ... LH1 SafeAbort`. v10 adds a separately advertised motion-safety capability for guarded stopped-print return. It is not yet the validated printing baseline until the watched Stop-and-return path passes.

## Why this is a Marlin fork

Little Hands keeps Marlin's proven step generation, SD reader, heater control, and thermal protections. The fork adds a small host protocol instead of replacing motion and temperature control. This keeps the safety-critical core close to Marlin 2.1.2.1 while letting the application stop reconstructing printer state from unrelated `M105`, `M27`, and `M114` replies.

## Capability discovery

`M115` advertises:

```text
Cap:LITTLE_HANDS_PROTOCOL:1
```

Hosts must keep the existing Marlin polling path when this capability is absent.

v10 additionally advertises:

```text
Cap:LITTLE_HANDS_SAFE_SD_ABORT:1
```

This means `M524` does not inject `EVENT_GCODE_SD_ABORT G28XY`. It does not by itself authorize a return move: Little Hands must have a trusted start before Stop and must receive a complete post-`M524` `M114` whose X/Y match the captured paused position in the same live session. Any restart, USB/session change, incomplete acknowledgement, changed X/Y, or manual jog revokes the permission.

## `M930` snapshot

`M930` emits one complete `LH1` line followed by Marlin's ordinary `ok`:

```text
LH1 token=123 seq=42 up=81000 sd=printing pos=1200 size=9000 lpx=10.000 lpy=20.000 lpz=0.200 lpe=3.000 spx=9.998 spy=20.001 spz=0.200 q=2 hot=199.750/200/127 bed=54.500/55/80
```

- `M930 S<uint32>` sets and echoes a volatile host-generated session token. A firmware reset clears the token to `0`.
- `M930 W` waits for the planner before reporting. It is for an already stopped/idle machine, not periodic print telemetry.

When `Cap:LITTLE_HANDS_PROTOCOL:1` is advertised, Little Hands uses one ordinary non-waiting `M930` as the primary periodic telemetry request. That single snapshot feeds the temperature graph, SD state/progress, logical position, planner depth, and firmware-session checks. It does not precede the snapshot with separate `M105`, `M27`, or `M114` requests; those commands remain the legacy path only for firmware without LH1. A rejected or incomplete snapshot from a known-LH1 session is retried later without adding legacy commands to the same exchange. This avoids mixing replies while the SD print owns most controller time.

The host reader waits up to four seconds for a complete `LH1` line and its following acknowledgement. A stale leading `ok` from an earlier exchange is ignored. If a known-LH1 printer returns only `echo:busy: processing` or otherwise does not produce a complete atomic line in that window, Little Hands keeps the last accepted observation and marks that M930 request as still pending. Later cycles listen for that same reply without sending another command; only after a 60-second pending limit may M930 be sent again. No immediate `M105`/`M27` fallback is added to the exchange. The operator log describes this as a temporary telemetry gap in the selected UI language and rate-limits repeated notices; it is not presented as a print or firmware failure.

For application or host-computer restart recovery, the active print state stores the bound token and last accepted sequence, uptime, and cursor atomically. A restored active marker must issue plain `M930` as its first printer-state query, even before a new `M115` capability reply has been collected, and compare the returned session. It must not send `M930 S...` and overwrite the retained firmware token. This is GUI reattachment to a print that the printer is already continuing autonomously, not G-code restart from the saved cursor. A match restores live telemetry plus explicit Pause, Stop, emergency heater controls, and verified Resume for a previously confirmed pause; jog/upload/restart/return remain blocked. Reattachment itself sends no print or motion command. A mismatch or malformed snapshot leaves the physical print autonomous and keeps unsafe controls blocked pending operator evidence.
- `seq` is a boot-local monotonically increasing snapshot number; `up` is firmware uptime in milliseconds.
- `sd` is `none`, `idle`, `selected`, `paused`, or `printing`; `pos/size` is the SD byte cursor.
- `lp*` is Marlin's logical commanded position.
- `sp*` is the position derived from step counters; `q` is the number of queued planner blocks.
- `hot` and `bed` are `current/target/power` triples.

The host accepts only a complete line and never combines fields from different replies. It must reject a changed/zero session token after binding, a decreasing sequence within one token, impossible SD cursors, and malformed heater triples.

## Safety boundary

Neither `lp*` nor `sp*` proves physical motion. The K9 has no trustworthy homing endstops or axis encoders; skipped steps and a moved unpowered axis remain invisible to firmware. `LH1` therefore improves telemetry and reset detection but does not authorize unattended return-to-start after reset, USB re-enumeration, motor-off, or uncertain motion.

The v10 SafeAbort workflow adds a session-bound guarded return gate while retaining visual operator confirmation and the validated segmented K9 motion profile. It never treats a capability or protocol acknowledgement alone as proof that the carriage or bed physically moved.

## Candidate artifact

The first build is:

```text
firmware/LH-v9-EXP-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-fan253-bed10k-max70-bedguard3c60s-lh1-mksLite.bin
sha256 3a9d190720678773c587ba5fbf3a2c08c897a636749df8e1f76ccae79fdbf6d2
```

The build and a non-motion serial test passed. `M115`, `M105`, `M27`, three sequential `M930` snapshots, and `M503` were verified after flashing; no heater or axis command was sent. Do not promote it as the normal printing baseline until Little Hands consumes `LH1` and an operator explicitly approves a watched print-path test.

The SafeAbort candidate artifact is:

```text
firmware/LH-v10-EXP-YZSwap-AutoFan45-FAN1-z600-e1040-watch180-fan253-bed10k-max70-bedguard3c60s-lh1-safeabort-mksLite.bin
sha256 32470ead999c363c4849f172fae315c1f2ae8f756a28651f2318857f7840c460
```

The reproducible PlatformIO build passed with flash usage `136932/262144` bytes and RAM usage `15200/49152` bytes. The 2026-10-10 flash and non-motion validation confirmed the v10 identity, both protocol capabilities, idle SD, fresh LH1, and zero heater targets/outputs. The first Stop-and-return movement still requires separate operator approval and direct observation.
