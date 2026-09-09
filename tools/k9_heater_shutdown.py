"""Bounded heater shutdown after a preheat failure; never move or start SD."""
import time
import math

import k9_marlin_sd as sdtool


class PreheatCancelled(RuntimeError):
    pass


def port_identity(port):
    return next((meta for meta in sdtool.list_serial_ports() if meta['device'] == port), None)


def matching_port(original, identity, candidates):
    safe = [meta for meta in candidates if sdtool.is_likely_printer_port(meta)]
    if not identity:
        return next((meta['device'] for meta in safe if meta['device'] == original), None)
    matches = []
    for meta in safe:
        if any(meta.get(key) != identity.get(key) for key in ('vid', 'pid')):
            continue
        serial = identity.get('serial_number')
        location = identity.get('location')
        if serial:
            same = meta.get('serial_number') == serial
        elif location:
            same = meta.get('location') == location
        else:
            same = meta['device'] == original
        if same:
            matches.append(meta['device'])
    return matches[0] if len(matches) == 1 else None


def heaters_are_off(values, require_bed):
    hotend, target, output, bed, bed_target, bed_output = values
    if hotend is None or not math.isfinite(hotend) or target != 0 or output != 0:
        return False
    if require_bed or any(value is not None for value in (bed, bed_target, bed_output)):
        return bed is not None and math.isfinite(bed) and bed_target == 0 and bed_output == 0
    return True


def shutdown_heaters(port, baud, parse_temperatures, *, identity=None, require_bed=True,
                     timeout_s=25.0, notify=lambda message: None):
    """Reconnect only to the identified printer; confirm fresh zero targets/output."""
    deadline = time.monotonic() + timeout_s
    errors = []
    last_reply = ''
    while time.monotonic() < deadline:
        candidate = matching_port(port, identity, sdtool.list_serial_ports())
        if not candidate:
            time.sleep(min(.5, max(0, deadline - time.monotonic())))
            continue
        try:
            with sdtool.open_serial(candidate, baud, timeout=.25) as ser:
                sdtool.sync_ascii(ser)
                for command in ('M108', 'M104 S0', 'M140 S0'):
                    try:
                        sdtool.send_line_wait_ok(ser, command, timeout_s=min(3.0, max(.1, deadline-time.monotonic())))
                    except Exception as exc:
                        errors.append(str(exc))
                # The first report can still show the preceding PWM interval.
                while time.monotonic() < deadline:
                    time.sleep(.5)
                    last_reply = sdtool.send_line_wait_ok(ser, 'M105', timeout_s=min(3.0, max(.1, deadline-time.monotonic())))
                    values = parse_temperatures(last_reply)
                    if heaters_are_off(values, require_bed):
                        return {'confirmed': True, 'port': candidate, 'reply': last_reply, 'errors': errors}
                    if values[1] not in (None, 0) or values[4] not in (None, 0):
                        break  # Reissue both off commands after a lost/garbled write.
        except Exception as exc:
            errors.append(str(exc))
        notify('Выключение нагрева пока не подтверждено; повторяю после восстановления USB.')
        time.sleep(min(.5, max(0, deadline-time.monotonic())))
    return {'confirmed': False, 'port': port, 'reply': last_reply, 'errors': errors}
