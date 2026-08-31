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

## v0.1.3 -> v0.1.4 -> v0.1.5 -> v0.1.6 -> v0.1.7 -> v0.1.8 -> v0.1.9 release evidence

The v0.1.3 release is intentionally preserved as the immutable zero-asset
predecessor (`release_id=379957493`, `asset_count=0`). The annotated v0.1.4
tag is also preserved as a failed-trigger counterexample: its target is the
v0.1.3 follow-up merge commit, its release is absent, and its tag-triggered
workflow runs failed before any job started. Neither the tag nor v0.1.3 is
rewritten or deleted. Its annotated tag object is
`074d8c01282f20efb55460a69a5177a378878f90` -> target commit
`480e23a159b533be23811667b68b09562ad4c4f8`; failed trigger run IDs are
`33429443119`, `33429524144`, and `33429601185`.

The annotated v0.1.5 tag is preserved as a second failed-trigger counterexample:
its release is absent, its tag object is
`1140c6701c65275bdf6e2cd7e801c9f8191b83ed` -> target commit
`bdee16c2506c0efdb3c5562f0d4126a293afc26f`, and failed trigger run IDs are
`33430206446`, `33430284845`, `33430367725`, and `33430500643`.

The annotated v0.1.6 tag is preserved as a third failed-trigger counterexample:
its release is absent, its tag object is
`cbe70a19dbf547868f907cb51954b66a0f774e66` -> target commit
`744e32655c6a6d1adf8c31d334814b555bce1a69`, and tag-triggered run
`33431118426` failed at runtime because the artifact ZIP request used an
unsupported `Accept: application/zip` header. The tag and its failed run are
not rewritten or deleted.

The annotated v0.1.7 tag is preserved as a fourth failed-trigger counterexample:
its release is absent, its tag object is
`1c3a06733538dc5f4ae3ec143c838984615e68d1` -> target commit
`a1682d56ec5d5c6ce5aaf1263a157a981d0e7e79`, and tag-triggered run
`33431644645` failed before creating release assets because a 404 response was
treated as a non-empty JSON value. The tag and failed run are not rewritten or
deleted.

The v0.1.8 tag is preserved with its failed draft release (`release_id=380007644`,
zero assets, `draft=true`, `immutable=false`). Its tag object is
`79a59ed5edb82a0d7d234525f897207ed3a59247` -> target commit
`4d04baa3dc0157a27f4fca2c3f4e3a9f929953c9`, and tag-triggered run
`33432034362` failed while uploading because the API endpoint used the REST
host instead of the release upload host. The tag and draft are preserved.

The tag-only v0.1.9 release workflow consumes the successful main CI evidence
artifact whose head SHA and observation source digest are identical to the
annotated v0.1.9 tag target. It packages the existing read-only evidence for
the released Gooo graph -> `main.tf.json` -> pinned OpenTofu `validate -json` ->
independent service oracle path. In caller-owned temporary storage it creates
exactly these four assets: `evidence-v0.1.9.tar.gz`,
`manifest-v0.1.9.json`, `SHA256SUMS`, and `source-v0.1.9.tar.gz`.

The workflow publishes v0.1.9 only after all four assets are present, then
checks the server-reported size and digest for every asset and verifies the
digest of every actual download. The manifest scopes `CLOSED` to this Gooo
semantic graph authority, leaves external utility `UNKNOWN`, and makes no
global core-authority claim. The release workflow itself performs no local
tests, builds, or OpenTofu execution.

## v0.2.0 generated OpenTofu service project

v0.2.0 uses `examples/intent/main.gooo` as the only human-authored semantic
source for a small `checkout-api` project. It declares two infrastructure
resources, one service capability, two service endpoints, and the bindings
that connect them. The twelve source activities are checked against the
released Gooo semantic graph and the fixed six-step user path.

GitHub Actions generates `main.tf.json`, `service-contract.json`, and
`relation-report.md`, then records `dossier.md` and `contract-receipt.json`.
The providerless artifact has three OpenTofu resources and zero modules. The
pinned OpenTofu 1.12.6 `validate -json` result is consumed by an independent
standard-library consumer that recomputes the source, graph, generated files,
validation, and relation-evidence digest chain.

The six examples are exactly two NORMAL, two UNKNOWN, and two REFUTED. Missing
service bindings remain UNKNOWN with a cause path and the six required fields:
`stage`, `step`, `reason`, `unknown_class`, `next_operation`, and
`blocked_by`. Contradictory resource/endpoint mappings are REFUTED, with
precedence `REFUTED > UNKNOWN > CLOSED`.

The released scope is `GENERATED_OPENTOFU_SERVICE_PROJECT_ONLY`. It leaves
external utility and global core authority explicitly unclosed. No handwritten
Go semantic authority exists; the repository inventory records zero Go files.
No exact before/after observation exists, so improvement remains UNKNOWN.
Release-time validation consumes the successful main CI artifact, executes no
local tests, builds, or OpenTofu commands, and preserves the v0.1.3–v0.1.9
history and failed-trigger evidence.
