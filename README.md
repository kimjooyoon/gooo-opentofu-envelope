# Gooo OpenTofu Envelope

This repository demonstrates a real, read-only infrastructure handoff: a
Gooo intent declares a built-in `terraform_data.hello` resource, the pinned
OpenTofu CLI validates and plans the generated JSON configuration, and the
resulting machine observation is bound back to the intent in a human dossier.

The boundary is deliberately narrow. GitHub Actions acquires checksum-locked
Gooo and OpenTofu releases, records `go version` for Go 1.27, then observes
only `version -json`, `validate -json`, the plan exit code, and `show -json`.
The plan file and every generated output live in caller-owned temporary
directories. No provider, credential, cloud, network, init, apply, destroy,
import, state mutation, or input-repository write is allowed.

The contract fixes twelve cells and twelve one-to-one Gooo activities, with
four cells in each proof family and indicator class. The evidence includes
at least three normal, three UNKNOWN, and three REFUTED cases, with precedence
`REFUTED > UNKNOWN > CLOSED`. UNKNOWN claims retain stage, step, reason,
unknown_class, next_operation, and blocked_by. A cache hit is never treated as
test-evidence reuse; because this example has no exact before/after pair,
improvement is reported as UNKNOWN.

The default branch began as the intentionally minimal `.gitignore`, `LICENSE`,
and `README.md` bootstrap. The implementation was added through a reviewed
pull request and is verified only by the Actions workflow. The workflow also
publishes an evidence artifact containing exact wall time, peak RSS, test
execution counts, artifact sizes/digests, Go/Gooo physical lines, repository
inventory, and zero-authority observations.
