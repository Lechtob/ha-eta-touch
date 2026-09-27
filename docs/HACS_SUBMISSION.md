# HACS default-catalog submission

Status: preparation only. `Lechtob/ha-eta-touch` is not currently included in
`hacs/default` (checked 2026-09-24). Using it as a HACS custom repository is separate
from acceptance into the default catalogue, and neither implies Home Assistant Core inclusion.

## Verified prerequisites

| Requirement | Evidence |
| --- | --- |
| Public, active GitHub repository | `Lechtob/ha-eta-touch`, default branch `main`, not archived. |
| Repository metadata | Description, topics and issue reporting are enabled. |
| Single integration | `custom_components/eta_touch`, with `manifest.json` and local brand assets. |
| HACS metadata | Root `hacs.json` specifies the integration name and minimum HA version. |
| HACS validation | `.github/workflows/hacs.yml` runs without ignored checks. |
| Hassfest | `.github/workflows/hassfest.yml` validates the integration. |
| Maintainer eligibility | The repository owner is `Lechtob`; submit from that personal account. |
| Published library | `py-etatouch-restful` 0.2.1 is available on PyPI. |

These are preparation checks, not a promise of acceptance. Recheck the released
files and successful action links immediately before submitting.

## Gate before submission

1. Complete the [1.0 hardware acceptance](RELEASE_CHECKLIST.md), resolve blocking
   findings, and publish the stable GitHub release from `main` after green CI,
   HACS and hassfest. Keep the RC as a pre-release until then. Waiting for stable
   1.0 is this project's release policy, not a claim that HACS requires version 1.0.
2. Use successful HACS and hassfest runs for the actual release contents. Do not
   use an older successful run to conceal failures in newer code.
3. Follow the current publishing instructions and PR template in `hacs/default`.
   Check that no open submission already exists before creating another one.
4. Confirm the standalone integration is still eligible: HACS does not accept
   custom integrations used only for alpha/beta testing Core integrations or
   overriding existing Core integrations. Future Core preparation does not turn
   this standalone HACS integration into a Core testing build.

The integration is not geographically restricted. German internal menu labels
are a compatibility limitation, not a restriction to a particular country.

## Prepared catalogue change

Fork `hacs/default` to the maintainer's personal account. Start a new branch from
the current upstream `master`, for example `codex/add-eta-touch`, and add exactly
one JSON string to the root `integration` array:

```json
"Lechtob/ha-eta-touch"
```

Keep the file's case-insensitive alphabetical ordering, JSON formatting and
trailing newline. Do not append blindly or modify unrelated entries. The existing
`lint jq` and `lint sorted` checks in the upstream repository must pass. Enable
maintainer edits on the PR; do not submit from an organization fork.

## Submission description preparation

Use the upstream template at submission time, filling every checklist item honestly.
Add a brief summary such as:

> ETA Touch provides local, read-only monitoring of ETA heating systems through
> the ETAtouch HTTP/XML interface. It includes grouped sensors, an active-error
> binary sensor, automatic discovery, configurable polling and diagnostics.
> The PU15 installation is field-tested; other models and firmware are not yet verified.

Required evidence to fill in after stable release:

- Current stable GitHub release URL: pending.
- Successful HACS action URL for the release contents, without ignored checks: pending.
- Successful hassfest action URL for the release contents: pending.
- Hardware acceptance summary and tested firmware: pending.

Do not describe the integration as officially listed before the upstream PR is
accepted. Do not request individual reviewers or submit duplicate PRs. The HACS
maintainers control review and acceptance timing; a green local workflow is not approval.

## After acceptance

Wait for HACS's catalogue scan, verify the integration is discoverable without
adding a custom repository, and then update the installation instructions. Continue
supporting existing custom-repository installations without changing the domain.

## Sources

- [Default-catalog inclusion](https://hacs.xyz/docs/publish/include/)
- [Integration requirements](https://hacs.xyz/docs/publish/integration/)
- [Official submission template](https://github.com/hacs/default/blob/master/.github/PULL_REQUEST_TEMPLATE.md)
- [Integration catalogue](https://github.com/hacs/default/blob/master/integration)
