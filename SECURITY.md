# Security Policy

## Important execution warning

WA Hunter compiles and executes native C++ programs. A timeout is not a
sandbox: submitted code may read files, start processes, consume resources, or
otherwise act with the permissions of the current user.

Do not run untrusted submissions with `wa_hunter.py` directly on a personal
computer or public server.

## Public-service requirements

Before accepting untrusted code, a deployment must provide all of the
following:

- a dedicated low-privilege service account;
- no network access for compilation and execution jobs;
- CPU, memory, process-count, output-size, and wall-clock limits;
- a fresh per-job working directory with strict permissions;
- no access to application secrets, databases, user homes, or host devices;
- bounded queue concurrency and request rate limits;
- automatic job cleanup and audit logs that contain no submitted secrets.

For the MVP, public GitHub requests should contain only code the requester has
explicitly chosen to publish. Execution remains manually reviewed and
controlled.

## Reporting a vulnerability

Do not include exploit code, secrets, or sensitive host information in a
public Issue. Contact the maintainer privately through the contact method on
their GitHub profile.
