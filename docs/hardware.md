# Arduino UNO indicator demo — hardware validation pending

Target: ATmega328P Arduino UNO, AVR core **1.8.6**, built-in libraries only. The same portable `control.h` is compiled for host and board. The sketch uses actual `millis()` and analog/GPIO input, unlike the host driver's virtual timestamps.

## Wiring

| Connection | Purpose |
|---|---|
| 10 kΩ potentiometer ends → 5V and GND | UNO analog reference input source |
| Potentiometer wiper → A0 | Raw ADC sample |
| D2 → normally closed switch → GND | Stop loop; open trips STOP_OPEN |
| D3 → removable jumper → GND | Explicit sample-valid input; remove to inject invalidity |
| Built-in D13 LED | Permission indicator only |
| USB | Power, commands and CSV logs at 115200 baud |

Do not connect any motor, relay, heater or mains circuit to the permission indicator. There is no independent hardware cutoff or certified safety architecture. Raw ADC values use UNO 0..1023; the example core deliberately accepts only 0..1000. Near the top of the potentiometer range, 1001..1023 produces RANGE rather than OVER_LIMIT. The D3 jumper simulates a validity signal; it does not automatically diagnose an unplugged potentiometer or plausible stuck reading.

## Compile and upload

```sh
arduino-cli core update-index
arduino-cli core install arduino:avr@1.8.6
arduino-cli compile --fqbn arduino:avr:uno firmware/fault_demo
```

Upload to the actual board port through Arduino IDE or CLI. No upload or physical testing is performed by the host runner. Serial logs are `millis,state,permit,fault_mask` after one startup banner.

## Manual bench experiment

1. Start with both jumpers closed and the potentiometer comfortably below 700 ADC counts. Boot must keep the LED off.
2. Send H at intervals **less than 300 ms** using a deliberate serial sender; manually typing H is generally too slow. After at least three samples, send R then A separately. Continue H approximately every 100 ms.
3. Stop heartbeats; verify the LED goes off and HEARTBEAT (8) appears. Timestamped Serial logs are software observations; use a logic analyzer to measure the physical output transition.
4. Restore H, then R and A. Open D2 or remove D3; verify fault and off indication. Restore inputs, wait for at least three healthy acquisitions, then explicitly reset and re-arm.
5. Raise the input to ≥800. Confirm trip; bring it down to ≤700 and demonstrate qualification/reset. Record actual thresholds/readings instead of claiming voltage calibration.

Physical work still required: wiring photo, board revision, actual tool versions, logic-analyzer traces, disconnected/stuck sensor behavior, interrupt or loop stalls, brownout/reset cause and LED pin behavior during reset. The watchdog is not configured by this sketch. A stalled MCU might leave a GPIO asserted; host timeout checks cannot protect against that.

An automated serial HIL adapter is future work. Compile success is the only board-specific evidence produced by CI in this version.
