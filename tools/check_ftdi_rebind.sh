#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: sudo $0 <usb-interface>"
  echo "Example: sudo $0 1-1.1.2:1.0"
  exit 2
fi

iface="$1"
driver_dir="/sys/bus/usb/drivers/ftdi_sio"

if [[ ! -e "$driver_dir/unbind" || ! -e "$driver_dir/bind" ]]; then
  echo "ftdi_sio bind/unbind files are not available"
  exit 1
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Please run with sudo: sudo $0 $iface"
  exit 2
fi

list_ttys() {
  python3 - <<'PY'
from serial.tools import list_ports
ports = [p for p in list_ports.comports() if p.device.startswith('/dev/ttyUSB')]
if not ports:
    print("(no ttyUSB devices)")
else:
    for p in ports:
        print(f"{p.device} {p.hwid}")
PY
}

echo "== before =="
list_ttys

echo
echo "== unbind $iface =="
echo "$iface" > "$driver_dir/unbind"
sleep 1
list_ttys

echo
echo "== bind $iface =="
echo "$iface" > "$driver_dir/bind"
sleep 1
list_ttys
