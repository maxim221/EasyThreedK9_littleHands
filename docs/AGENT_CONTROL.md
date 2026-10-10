# Local Agent Control And Telemetry

Little Hands exposes an owner-only local control socket while the GUI is
running. Terminal tools and an assisting agent can inspect and operate the same
application state without moving the desktop pointer or opening a second serial
connection.

The bridge runs inside `K9ControlCenter`. Commands keep the existing
single-worker lock, trusted-home rules, recovery markers, suspect-upload blocks,
power-cycle gate, and heater cleanup. It is not a raw G-code terminal.

## Read status

```bash
python3 tools/k9_agent_cli.py status
python3 tools/k9_agent_cli.py sd-files
python3 tools/k9_agent_cli.py log-tail --lines 120
```

`status` includes Control Center / USB health, the current asynchronous
operation, hotend and bed current/target/power with sample age, SD and print
state, position freshness, home trust, recovery gates, USB generation, and the
latest strict `LH1` snapshot when supported.

For scripts, `watch` emits one compact JSON object per line:

```bash
python3 tools/k9_agent_cli.py watch --interval 5
python3 tools/k9_agent_cli.py watch --interval 1 --count 30 > /tmp/lh-watch.jsonl
```

Little Hands keeps legacy `M105` / `M27` / `M114` polling active. On LH v9 it
also binds a fresh volatile host token and records atomic `M930` snapshots.
Malformed snapshots, token mismatches, impossible cursors, and backwards
sequence/uptime are rejected. LH1 coordinates remain telemetry, not proof of
physical motion.

## Commands and confirmations

Use `python3 tools/k9_agent_cli.py --help` and subcommand help for the full list.
State-changing commands require an exact acknowledgement, for example:

```bash
python3 tools/k9_agent_cli.py jog X 5 --confirm operator-watching
python3 tools/k9_agent_cli.py hotbed 35 --confirm operator-watching
python3 tools/k9_agent_cli.py upload-gcode gcode/model.gcode --confirm write-printer-sd
python3 tools/k9_agent_cli.py heaters-off --confirm safety-shutdown
python3 tools/k9_agent_cli.py save-start --confirm physical-start-verified
python3 tools/k9_agent_cli.py start MODEL.GCO --confirm physical-start-and-watch
```

An accepted hardware command is asynchronous. Poll `status.operation` until it
is `completed` or `failed`. `accepted` means the existing worker took the job;
it does not mean a move, heat cycle, upload, or print physically succeeded.

Upload and start are deliberately separate commands. A successful
`upload-gcode` never sends `M24`; inspect the resulting SD list and then request
`start` separately with the operator watching the printer.

Before any jog or print start, the assisting agent must still ask the operator
to watch the printer. Never infer physical motion from `ok`, `M114`, or LH1
logical/step-counter coordinates.

## Local security

The Unix socket lives in the current user's short runtime directory and is mode
`0600`. Its token is `monitor_logs/little_hands_control.token`, also mode
`0600`. The server accepts only local Unix-socket clients and removes the socket
when the GUI closes. Do not copy the token into logs, issues, or chat messages.
