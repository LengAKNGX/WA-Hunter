# `lenga.com.cn` migration plan

This records the migration used to turn the existing lightweight OJ into the
hosted WA Hunter service. Production switched successfully on 2026-10-02;
the sequence below remains the rollback and maintenance reference.

## Existing foundation

The current service already provides the expensive security and infrastructure
pieces needed by WA Hunter:

- Nginx with HTTPS and the required ICP footer;
- registration, login, CSRF protection, and secure session cookies;
- SQLite persistence;
- C17, C++17, and Python compilation;
- a low-privilege systemd service account;
- Firejail execution with no network, dropped capabilities, process/file limits,
  private temporary directories, and a dedicated executable job root.

The existing problem-list interface and fixed hidden test cases are not central
to the new product and may be removed after migration.

## Target user flow

```text
Landing page
    |
register / log in
    |
new hunt: problem URL + solution.cpp + brute.cpp + bounded config
    |
queued job (global concurrency = 1)
    |
compile both programs in Firejail
    |
generate -> execute -> compare -> update strategy
    |
minimize the first mismatch
    |
private result page: report + counterexample
    |
administrator marks the ¥1 delivery as confirmed
```

## Database migration

Keep `users` and `sessions`. Back up the database before every schema change.
Add a `hunts` table containing:

- owner user ID and timestamps;
- optional public problem URL;
- candidate and oracle C++ source;
- bounded generation parameters and seed;
- `queued`, `running`, `found`, `not_found`, or `failed` status;
- selected strategy and iteration count;
- original and minimized cases;
- both program outputs and execution statuses;
- a short error field;
- delivery state (`unconfirmed` or `paid`) and `paid_at`.

Results and source must be visible only to their owner and administrators.
Public GitHub Issues should remain an alternative only for code the requester
has deliberately chosen to publish.

## Worker isolation

Run hunts in a separate systemd worker, not inside the HTTP request thread.
The web service inserts bounded jobs; one worker consumes them serially. Use a
fresh directory for every hunt under a dedicated WA Hunter job root.

The worker must preserve or strengthen the existing controls:

- Firejail `--net=none`, `--private`, `--private-dev`, `--private-tmp`,
  `--noroot`, dropped capabilities, seccomp, and no-new-privileges;
- explicit blacklists for the application database, `/root`, SSH material, and
  unrelated service directories;
- compilation and execution CPU/wall-clock limits;
- memory, output, file-size, open-file, and process-count limits;
- a maximum source size, array length, value range, iteration budget, and queue
  length;
- automatic cleanup whether a job succeeds, fails, or times out.

Do not expose a general shell, arbitrary compiler flags, custom execution
commands, filesystem inputs, or network access.

## Recommended public MVP limits

- language: C++17 only;
- input model: one integer array (`n` then `n` integers);
- `1 <= n <= 40` for generated cases;
- at most 100 initial cases per hunt;
- at most 100 minimization checks;
- at most one running job and five queued jobs globally;
- one active hunt per user;
- candidate/oracle source at most 64 KiB each;
- execution timeout at most one second per program;
- result output retained at a small fixed maximum.

These caps fit a classroom-scale service on a two-core, 2 GB server. Reject
excess work instead of increasing concurrency under load.

## Safe migration sequence

1. Put the current service into a short maintenance window.
2. Copy the application, database, systemd unit, Nginx config, and job-sandbox
   scripts to a timestamped backup directory outside the web root.
3. Verify the backup file list and SQLite integrity before changing anything.
4. Add the new schema without deleting existing users or submissions.
5. Deploy the WA Hunter web process and separate single-concurrency worker.
6. Test compilation, candidate/oracle execution, timeouts, output limits, and
   filesystem/network isolation from the worker's own systemd namespace.
7. Test one known-correct pair and the repository's known-buggy demo.
8. Switch the home page to WA Hunter and retain the old OJ at a temporary
   administrator-only route during the observation period.
9. After the new service is verified and the backup is recoverable, remove old
   problem and submission UI if desired. Database deletion is optional and
   should be a separate, deliberate step.

## Rollback condition

If login, queue processing, sandboxing, or the known demo fails after the
switch, restore the previous application and systemd unit, point Nginx back to
the old process, and retain the new database tables for diagnosis. A failed
migration must never be “fixed” by weakening Firejail or service isolation.
