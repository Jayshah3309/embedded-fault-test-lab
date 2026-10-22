# Embedded Fault Testing Lab

**Prove how a controller responds when inputs fail.** This lab injects deterministic faults into a compiled C++ controller, checks every response against explicit expectations, and writes JSON, HTML and JUnit reports.

Newly authored with AI assistance for Jay Shah's embedded systems portfolio. The same portable controller header is used by the native test driver and an Arduino UNO indicator demo. This is an educational reference, not a certified safety system, physical reliability measurement, or validation of every other repository.

## Run locally

Requires **Python 3.10+ and g++ with C++11 support**. No Python packages or hardware are required.

```sh
python lab.py --sanitize --mutations
python -m unittest discover -s tests -v
```

Open `reports/report.html` in a browser. The runner also creates `report.json`, `junit.xml`, and (with `--mutations`) `mutations.json`. Reports include per-step inputs, expected/actual outputs, compiler version, source/scenario SHA-256 hashes and UTC execution time. `--sanitize` enables UndefinedBehaviorSanitizer on the host build; it is not a complete memory-safety proof.

For Windows, use WSL with Python and g++, or a native C++ toolchain accessible as `g++`; the runner uses argument arrays without a shell. Native Windows toolchain compatibility has not been executed during authoring. Reports are overwritten on each run, so copy evidence you want to retain.

## Implemented

| Area | Behavior |
|---|---|
| Fault scenarios | 20 named cases covering invalid/range inputs, stale readings, heartbeat loss, stop loop, malformed commands, over-limit trip, recovery and clock behavior |
| Recovery | Latched faults; three healthy samples; explicit reset to READY; separate arm to ACTIVE |
| Timing | 499/500 ms sensor boundary, 299/300 ms heartbeat boundary and uint32 rollover |
| Negative controls | Three deliberately broken host-only variants must be detected |
| Harness checks | Nine unit tests including invalid schema, malformed frames, failed expectations, missing compiler, and escaped HTML reporting |
| Embedded target | Arduino UNO sketch uses the same `control.h`; built-in LED is the permission indicator |
| CI | Python 3.10/3.12 host runs, report artifacts and UNO AVR compilation |

## Controller example

This supervisor accepts a unitless sensor value from 0 to 1000. At 800 it trips; recovery requires values at or below 700. Sensor freshness expires at 500 ms and the active-state heartbeat at 300 ms. These are **example engineering requirements**, not calibrated limits for a real machine.

`H` heartbeat → three healthy samples → `R` reset → `A` arm. `X` stops. Good data alone never clears a fault, and reset never directly asserts permission. The UNO demo controls only its built-in LED.

## Learn and extend

- [Design and protocol](docs/design.md): exact state/timeout semantics and fault bitmask.
- [Hardware guide](docs/hardware.md): UNO wiring, safe indicator demo and unperformed physical trials.
- [Verification evidence](docs/testing.md): local results, CI references and limits.
- [Scenario file](scenarios/regression.json): edit explicit inputs/expectations, then run `python lab.py --scenarios PATH --out reports/custom`.

Exit status **0** means all requested checks passed; **1** means an expectation failed or a mutation escaped; **2** means invalid input, compiler/tool failure or timeout. A failed invocation can leave older report files, so verify exit code, UTC timestamp and hashes before using evidence.

## Scope and next work

Host execution validates software behavior under the supplied virtual event schedule. It does not measure interrupt latency, GPIO timing, sensor electronics, power-loss recovery or a physically stuck output. Calling a tick at a timestamp is not proof that real firmware meets that deadline. Physical HIL, logic-analyzer traces, watchdog/reset-cause experiments and adapters for the racing-car/waste-sorter repositories remain future work. Those repositories were not modified by this project.

No license grant has been selected yet. Do not infer one from public visibility.
