# Verification evidence

## Local execution — 22 October 2026

On Python 3.12 with g++, the following commands completed successfully:

```sh
python lab.py --sanitize --mutations
python -m unittest discover -s tests -v
```

- **20/20 scenarios passed**, using actual native execution of the portable C++ core.
- **3/3 deliberately broken host variants detected**: missing stale timeout, heartbeat timeout and threshold trip.
- **9/9 harness tests passed**, including a subprocess CLI regression, invalid input, failed expectations and compiler failure behavior.
- UndefinedBehaviorSanitizer enabled for the main scenario/mutation run; no reported undefined behavior.

The test suite deliberately creates a failed scenario while checking that wrong expectations produce CLI exit code 1. That nested failure is expected; the enclosing unittest must still show OK. The first local stale-boundary scenario also exposed a test-schedule mistake: it inadvertently expired the heartbeat while trying to isolate stale sensor data. Explicit intermediate heartbeat events were added; the final scenario file isolates the intended 499/500 ms boundary. No controller behavior was weakened to make it pass.

## CI

The committed workflow runs Python 3.10 and 3.12 on Ubuntu 24.04, saves generated reports as Actions artifacts, and compiles the UNO sketch against AVR core 1.8.6. [Verified CI run](https://github.com/Jayshah3309/embedded-fault-test-lab/actions/runs/39779425856), commit `c4506268f47067d03199e2665e24604b1e19bdb7`, completed successfully on 22 October 2026: **host (3.10), host (3.12), and uno all passed**. Each host job ran the nine harness tests plus all 20 scenarios and three mutation checks with undefined-behavior instrumentation. Both report bundles are available under the run’s Artifacts section (`fault-lab-python-3.10` and `fault-lab-python-3.12`).

GitHub emitted Node 20 deprecation warnings for the setup/checkout/artifact actions; those actions ran successfully under the runner’s compatibility behavior. Compilation confirms target compatibility, not physical validation.

## What the evidence does not establish

No board, sensor, logic analyzer or attached actuator was available to this workflow. Virtual timestamps do not establish measured detection latency. The sample-invalid flag is injected, not an electrical sensor diagnosis. Reset starts a new native controller instance, not a validated power-loss recovery path. GPIO startup/transient behavior and stalled-MCU protection remain untested. No claim of standards compliance, complete fault coverage or certification is made.

## Reproduce and compare evidence

Every successful or expectation-failing normal run writes `report.json`, `report.html` and `junit.xml`; mutation mode also writes `mutations.json`. Inspect generated time, core/driver/scenario hashes and exit status. Tool/schema failures exit 2 and may leave prior output files untouched. Use a new `--out` directory per experiment when preserving evidence. Do not commit someone else's real device logs, private serial identifiers or measured results as synthetic fixtures.
