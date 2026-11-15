# WA Hunter Architecture

## Design goal

WA Hunter should have one definition of “generate a case” and “minimize a
counterexample”, while allowing different execution environments. The local CLI
runs trusted development binaries directly; the hosted service runs untrusted
programs through Firejail and resource limits. Search semantics must remain the
same in both paths.

## Current layers

```text
┌──────────────────────────────────────────────────────────┐
│ Interfaces                                               │
│ CLI (wa_hunter.py)        Web / admin / payment routes   │
├──────────────────────────────────────────────────────────┤
│ Orchestration                                            │
│ compile → generate → execute → compare → minimize        │
├──────────────────────────────────────────────────────────┤
│ Shared deterministic core (server/core.py)               │
│ strategies · seeded generation · encoding · minimization │
├───────────────────────┬──────────────────────────────────┤
│ Local executor        │ Hosted executor                  │
│ subprocess + timeout  │ Firejail + prlimit + no network  │
├───────────────────────┴──────────────────────────────────┤
│ Hosted persistence: SQLite queue, audit and delivery     │
└──────────────────────────────────────────────────────────┘
```

### Shared deterministic core

`server/core.py` contains only pure or deterministic search primitives:

- the canonical seven-strategy registry;
- seeded array generation and feedback-adjusted weights;
- array input encoding;
- deletion-based Delta Debugging;
- bounded value shrinking;
- an optional minimization-check budget for hosted execution.

It deliberately does not import the database, HTTP server, Firejail, subprocess
runner, DeepSeek client, or payment code. This makes it fast to test and safe to
reuse.

### Execution adapters

The CLI and hosted service retain separate execution adapters because their
trust models differ:

- the CLI uses normal local subprocesses and is intended for code the operator
  chose to run;
- the hosted service uses a low-privilege account, Firejail, no network, and
  explicit CPU, memory, process, file, and output limits.

Combining these adapters would either weaken production isolation or make local
development unnecessarily complex.

### Hosted orchestration and persistence

`server/app.py` owns stateful behavior: users, sessions, CSRF, SQLite migrations,
task states, the single worker, Oracle review, invalidation, payment verification,
and delivery access. It calls the shared core but remains responsible for hard
service budgets such as `MAX_MINIMIZE_CHECKS`.

## Structural improvement completed

Previously, the CLI and server each contained their own generator and minimizer.
Their `boundary` strategy had already diverged, so a test run could differ merely
because it was launched through another interface. The duplication has been
removed. Both interfaces now import the same implementation, and tests assert
that the hosted alias points to the shared generator.

The second refactoring step introduced `HuntEngine`. It owns the common
generate/execute/compare/feedback/minimize loop and receives an executor callback.
The CLI injects its local subprocess pair; the hosted worker injects its
Firejail-backed pair. Search decisions are shared without weakening isolation.

Deployment must copy `server/app.py` and `server/core.py` together. A deployment
that updates only `app.py` is incomplete.

## Proposed next structural changes

### 1. Evidence model

Create a versioned `HuntEvidence` structure containing authoritative constraints,
seed, strategy counts, original input, minimized input, outputs, statuses, and
Oracle review level. Markdown, HTML, and downloads should render from this one
object instead of assembling conclusions independently.

### 2. Versioned input schemas

Replace hard-coded array assumptions with small, reviewed schema plugins. Start
with `integer_array/v1`; later add strings or graphs only when each schema has a
validator, generator, encoder, and shrinker. The model may propose a schema but
must never bypass its deterministic validator.

### 3. Repository boundary for infrastructure

Keep production configuration, migrations, and deployment checks in explicit
modules rather than allowing `app.py` to grow indefinitely. Good next splits are
`storage.py`, `sandbox.py`, `oracle.py`, and `web.py`; they should be extracted
only with characterization tests to avoid a large unsafe rewrite.

### 4. Deployment contract test

Add a smoke test that starts the service exactly as systemd does, verifies the
shared core import, submits a known faulty pair, and checks the resulting evidence.
This catches “local tests pass but the server package is incomplete” failures.

## Non-goals

- The core does not prove program correctness.
- LLM output is not an authoritative constraint source.
- The hosted service must not weaken isolation to simplify code reuse.
- New input families should not be added before their validators and shrinkers
  have deterministic tests.
