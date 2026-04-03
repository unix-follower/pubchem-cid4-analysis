# Crow Load Tests

This directory contains the first-pass load-testing toolkit for the C++ Crow HTTPS backend. It covers the same read-only route mix across three tools:

- Apache JMeter
- Gatling
- k6

The current target is the Crow server in `cpp/`. The scenarios exercise these endpoints:

- `GET /api/health`
- `GET /api/cid4/conformer/1`
- `GET /api/cid4/structure/2d`
- `GET /api/cid4/compound`
- `GET /api/algorithms/pathway`
- `GET /api/algorithms/bioactivity`
- `GET /api/algorithms/taxonomy`

## Start the Crow server

From the repository root:

```bash
cd cpp && cmake -S . -B build && cmake --build build --target crow_api_server -j4
cd cpp && ./build/crow_api_server --host 127.0.0.1 --port 8443
```

The examples below assume `https://127.0.0.1:8443`.

## Prepare a Java truststore

The repo's demo HTTPS certificate is self-signed. `k6` can skip verification, but JMeter and Gatling need a Java truststore that includes the demo cert.

From the repository root:

```bash
rm -f load-tests/tmp/cid4-demo-truststore.p12 && \
keytool -importcert -noprompt -alias cid4-demo-ca \
  -file data/out/crypto/cid4_crypto.demo.cert.pem \
  -keystore load-tests/tmp/cid4-demo-truststore.p12 \
  -storetype PKCS12 \
  -storepass changeit
```

## k6

The k6 script is the simplest starting point because it can run directly against the self-signed server.

```bash
k6 run \
  -e BASE_URL=https://127.0.0.1:8443 \
  -e VUS=20 \
  -e DURATION_SECONDS=30 \
  -e PAUSE_MS=200 \
  load-tests/k6/crow-api.js
```

Useful environment overrides:

- `BASE_URL` default: `https://127.0.0.1:8443`
- `VUS` default: `20`
- `DURATION_SECONDS` default: `30`
- `PAUSE_MS` default: `200`

## Apache JMeter

The JMeter plan uses a single thread group and loops over the same mixed GET route set.

```bash
JVM_ARGS="-Djavax.net.ssl.trustStore=$(pwd)/load-tests/tmp/cid4-demo-truststore.p12 -Djavax.net.ssl.trustStorePassword=changeit" \
jmeter -n \
  -t load-tests/jmeter/crow-api-load-test.jmx \
  -Jhost=127.0.0.1 \
  -Jport=8443 \
  -Jprotocol=https \
  -Jthreads=20 \
  -JrampSeconds=10 \
  -JdurationSeconds=30 \
  -l load-tests/results/jmeter-crow.jtl \
  -e -o load-tests/results/jmeter-crow-report
```

Property overrides:

- `host` default: `127.0.0.1`
- `port` default: `8443`
- `protocol` default: `https`
- `threads` default: `20`
- `rampSeconds` default: `10`
- `durationSeconds` default: `30`

## Gatling

The Gatling simulation uses a steady users-per-second profile after a short ramp period.

```bash
export GATLING_HOME=/path/to/gatling
JAVA_OPTS="-Djavax.net.ssl.trustStore=$(pwd)/load-tests/tmp/cid4-demo-truststore.p12 -Djavax.net.ssl.trustStorePassword=changeit" \
  "$GATLING_HOME/bin/gatling.sh" \
  -s CrowApiSimulation \
  -sf "$(pwd)/load-tests/gatling/user-files/simulations" \
  -rf "$(pwd)/load-tests/results/gatling" \
  -DbaseUrl=https://127.0.0.1:8443 \
  -DusersPerSecond=20 \
  -DrampSeconds=10 \
  -DdurationSeconds=30 \
  -DpauseMillis=200
```

System property overrides:

- `baseUrl` default: `https://127.0.0.1:8443`
- `usersPerSecond` default: `20`
- `rampSeconds` default: `10`
- `durationSeconds` default: `30`
- `pauseMillis` default: `200`

## Suggested run order

Use the same machine, the same Crow binary, and as little background noise as possible.

1. Run the k6 scenario first as a quick sanity check.
2. Run JMeter for a thread-heavy comparison.
3. Run Gatling for a steady arrival-rate comparison.
4. Repeat each test three times and keep the median result.

## How to classify results

These bands are developer-workstation guidance for this repo's small JSON responses. They are not production SLOs.

| Signal | Good | Normal | Bad |
| --- | --- | --- | --- |
| Error rate | `0%` | `>0%` and `<=1%` | `>1%` |
| p95 latency | `<=150 ms` | `>150 ms` and `<=500 ms` | `>500 ms` |
| p99 latency | `<=300 ms` | `>300 ms` and `<=1000 ms` | `>1000 ms` |
| Median throughput vs your local baseline | `>=90%` | `>=60%` and `<90%` | `<60%` |
| Run-to-run spread across 3 repeats | `<=10%` | `>10%` and `<=25%` | `>25%` |

### Baseline-relative evaluation

Use this when comparing code changes on the same machine.

1. Choose one tool and one parameter set.
2. Run it three times on a known-good revision.
3. Record the median throughput and latency as the local baseline.
4. Compare new revisions against that baseline.

Treat the result as bad even if the absolute throughput still looks high when any of these are true:

- error rate increases above `1%`
- p95 latency doubles relative to baseline
- throughput drops below `60%` of baseline

### Absolute guidance

Use this for a quick local check when no baseline exists yet.

- Good usually means the server stays at `0%` errors and keeps p95 below `150 ms` during a 20-user, 30-second run.
- Normal usually means the server still works correctly but latency is visibly elevated or throughput is inconsistent.
- Bad usually means requests fail, latency spikes above `500 ms` at p95, or throughput collapses relative to repeated runs.

## Output locations

Generated reports should stay under `load-tests/results/`.

- JMeter raw results: `load-tests/results/*.jtl`
- JMeter HTML report: `load-tests/results/jmeter-crow-report/`
- Gatling reports: `load-tests/results/gatling/`
- k6 console summary: capture or redirect it if you need to archive it
