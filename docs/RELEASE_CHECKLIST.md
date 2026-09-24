# Release acceptance: 1.0.0

Candidate: `1.0.0-rc.1`. Final release approval is **pending hardware testing**.
CI uses mocked ETA transport and cannot establish multi-day operation on a boiler.

## Stable scope

- Read-only measurements, status values, counters and the active-error binary sensor.
- Curated discovery and manual URI selection, grouped by functional block.
- UI setup, connection reconfiguration, polling/discovery options and migration.
- English/German entity names and privacy-preserving diagnostics.
- No climate entities, setpoint writes, heating-mode changes or expert controls.

Keep entry and entity identity stable within the 1.x series. Treat changes to
unique IDs, units, counter semantics, saved options and the default discovery set
as compatibility-sensitive changes that need explicit tests and release notes.
Known limitations remain: German internal menu paths, name-based block grouping,
no verified hardware serial identity, and only the PU15 installation field-tested.
Do not advertise universal ETA model/firmware compatibility.

## Automated release gates

- [ ] Library 0.2.1 is available from PyPI; the manifest and both test environments pin it.
- [ ] Full tests and config-flow line/branch coverage pass on HA 2026.8.0 and 2026.9.3.
- [ ] CI, HACS and hassfest pass on the exact integration release commit.
- [ ] The release tag points to the reviewed code and matches the manifest version.
- [ ] Release notes explain minimum HA version, read-only scope and version-3 migration.

The PR checks and workflow logs are the evidence for these gates. Recheck them
for each new candidate; do not assume earlier results apply after code changes.

## Hardware acceptance

Before installing: record HA version, ETA firmware, current integration version,
and the entity IDs/custom names you rely on. Create and retain a Home Assistant
backup that includes configuration and the installed integration.

- [ ] Update an existing 0.4.1 installation through HACS and restart HA.
- [ ] Confirm existing entities, custom names and device assignments are retained.
- [ ] Check boiler, hot water, rooms, pellet stock, outside temperature and diagnostics
      against the controller display. Compare at approximately the same time.
- [ ] Verify all four previously affected runtime sensors remain numeric and available.
- [ ] Check consumption totals and statistics for new unit/reset warnings or implausible jumps.
- [ ] Change the polling interval and verify successful updates at the new interval.
- [ ] Change the manual selection, clear it to return to discovery, and restore the
      intended configuration. Re-selected URIs must retain their entity IDs/custom names.
- [ ] Reload the integration and restart HA again; no duplicate entities or errors.
- [ ] Observe normal heating/hot-water activity for at least 48-72 hours. Record any
      recurring errors, unexpected unavailable states or excessive log growth.
- [ ] Confirm recovery if a connection interruption occurs. Do not switch off the
      boiler or interrupt safety-related equipment for this test. Controlled outage
      and recovery behavior is already covered by mocked automated tests.

No write tests are necessary. Absence of active boiler errors is not evidence
that every integration function is correct. If a candidate fails, record the
symptom and a reviewed diagnostics download, fix it, and issue another candidate.

## Acceptance record

- Tester / installation: pending
- HA version / ETA firmware: pending
- Installed candidate and start/end of observation: pending
- Upgrade/migration result: pending
- Measurements/statistics comparison: pending
- Options/reload/recovery result: pending
- Log findings and unresolved issues: pending
- Final 1.0.0 approval: pending

Keep private hostnames, serial numbers, personal room names and unredacted logs
out of public PRs and issues. A concise sanitized result is sufficient.

## GitFlow publication

1. Publish the tested library first; verify its version on PyPI before pinning it.
2. Prepare the integration candidate on `release/1.0.0`, with green checks and
   matching manifest/tag. Publish it as a GitHub **pre-release**, not latest stable.
3. Test the candidate in Home Assistant. Keep `main` on the existing stable release
   until acceptance is complete; do not merge an unaccepted RC into the stable branch.
4. After acceptance, update the release branch to `1.0.0`, finalize the changelog
   and rerun all gates. Merge the release PR into `main`, publish the stable tag,
   then merge `main` back into `develop` without losing release changes.
5. Do not claim Core inclusion or HACS default-catalog inclusion based on this release.
