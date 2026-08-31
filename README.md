# Gooo OpenTofu Service Contract Envelope

This repository closes one deliberately small path:

`Gooo service-infrastructure contract -> generated main.tf.json -> OpenTofu validate -json -> independent semantic oracle`

The `.gooo` input declares a `web` service with type `http`, port `8080`, the
`APP_ENV=production` environment, three required outputs, and four semantic
relations. The workflow obtains checksum-locked releases, dumps the released
Gooo graph, verifies its authoritative `.gooo`/IR boundary and every
`used`/`wasGeneratedBy` activity port, generates providerless OpenTofu JSON,
and runs the pinned OpenTofu CLI at the machine-readable `version -json` and
`validate -json` boundary.

The generated artifact is exactly `main.tf.json`, `contract-receipt.json`, and
`dossier.md`. The receipt carries checksum verification, binary digest, version
JSON digest, validation exit code, diagnostic counts, and the immutable
source -> released IR -> generated JSON -> OpenTofu observation -> independent
oracle chain. The oracle checks service values, types, required outputs, and
relations; a template's mere presence cannot close the case.

The default profile is read-only. It forbids provider installation, init
download, plan/apply/destroy/import, state/backend access, credentials, cloud or
network infrastructure access, `tofu test`, and TF_ACC acceptance tests. A
separate authorized profile is required for acceptance testing and is outside
this envelope. Existing Terraform-compatible names are not treated as product
identity: the receipt identifies the engine as `OPENTOFU 1.12.6` from the
pinned release lock.

The denominator is fixed at twelve cells and twelve one-to-one Gooo activities:
FOUNDATION, COHERENCE, and REGRESSION each have four proof cells; DRIVER,
OUTCOME, and GUARDRAIL each have four indicator cells. Canonical cases are
normal=3, UNKNOWN=3, REFUTED=3, with `REFUTED > UNKNOWN > CLOSED`. Every
UNKNOWN has `stage`, `step`, `reason`, `unknown_class`, `next_operation`, and
array-valued `blocked_by`; a directly missing input uses an empty array.

Verification phases record `EXECUTED`, `REUSED`, `SKIPPED`, or
`NOT_APPLICABLE` independently from cache `HIT`, `MISS`, `DISABLED`, or
`UNKNOWN`. Installation binary cache, Go build cache, and prior test-evidence
reuse are separate fields. Runner persistence is `EPHEMERAL`, `PERSISTENT`, or
`UNKNOWN`; a binary cache hit never means test evidence was reused. Prior
evidence is eligible only when all eight reuse-key fields match:
source, toolchain, command, config, dependency, provider-lock,
test-inventory, and policy digests. Reuse is never reported as a zero-millisecond
current-run execution.

No exact before/after pair exists in this use case, so performance improvement
and user utility remain `UNKNOWN`. The workflow records exact integer wall
milliseconds, peak RSS KiB, test counts, replay comparisons, artifact
files/bytes, Go/Gooo file and physical-line counts, repository subfolders,
repository writes, and external mutation counts. The root README is excluded
from repository inventory; non-empty repository status is a read-only boundary
failure rather than silently reported as zero writes. Core semantic authority
is `CLOSED` only when the released Gooo IR, pinned OpenTofu JSON validation, and
independent service oracle all provide evidence; utility remains explicitly
unclosed until a before/after user observation exists.
