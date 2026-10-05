# TaskFlow — Current handoff

## 2026-10-05: local project-scoped agent bridge

TaskFlow now supports user-initiated project batches through a local command bridge. Adding a task never launches an agent. The current implementation does not include an MCP server, network service, or paid API.

### Current behavior

- Local SQLite is the shared task store. Legacy JSON is imported once, preserving original bytes and a pre-sqlite backup. Legacy IDs, notes, dates, preferences and extra fields remain. Invalid input is rejected without replacing the source with empty data.
- Per-task transactions, revision checks and exclusive claims preserve simultaneous desktop/agent edits. Stale settings saves merge only changed fields. User edits, manual completion and requeue invalidate older claims.
- Project menus configure private local repo / optional OZI project-directory bindings and copy a scoped agent prompt. Bindings stay in the local database.
- TaskFlowAgent.exe lists, claims and reports tasks; checks project/repo/revision/token; and never executes commands or launches agents. A completed report requires evidence text. Explicit review-required tasks become needs_review. Evidence is the agent's report; the bridge does not independently rerun tests.
- Compact card metadata shows in-progress, review and blocked states. Task menus display results, require human review and requeue interrupted tasks. External changes refresh every 1.5 seconds without clearing the entry field.
- OZI TODO.md is a projection of the same store. Only UUID-scoped TaskFlow markers are replaced; other notes survive. Corrupt/unavailable projections preserve primary task data and emit warnings. Task edits never automatically commit or push.
- Setup bundles desktop and agent executables. CI tests the bridge and builds all three download artifacts. Personal data, databases, backups and env files are ignored by Git.

### Verification

- Offscreen unittest run: 28 passed. Coverage includes migration, concurrent claims/additions, stale updates, task revision invalidation, review-required completion, repo/project isolation, projection preservation, rebinding/deletion, CLI integration, GUI refresh and installer copy behavior.
- RGB screenshots of the ordinary main screen match the previous source revision pixel-for-pixel at 440x640 and 340x460. New connection dialog and review state were visually inspected using synthetic data. Existing design, typography, spacing, border and resize behavior remain.
- Impeccable detector emitted advisory token/schema mismatches against the older design record; this was not a clean detector result. No unrelated design migration was performed.
- Frozen GUI verification passed: startup, SQLite, external-result refresh, compact dimensions and bundled icon, using a disposable profile with no real data or startup writes.
- Frozen agent executable completed a real read/claim/report round trip and updated a synthetic TODO projection.
- Setup archive payload hashes match the tested binaries. Installer tests copied both tools and requested two shortcuts in a mocked profile. A real-profile installation of this new setup was not performed during verification.
- Graphify AST update: 278 nodes, 536 edges, 17 communities; no LLM/API used. Generated output remains ignored.

### Local build artifacts

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| dist_next/TaskFlow.exe | 56291837 | e7d849edf564c6231b728de926104cc55e40c15900dc87a58aec5a4d54a8693b |
| dist_agent/TaskFlowAgent.exe | 9607153 | 5250ee2d246fd5ff6fb751ef5ed49c152b9a377208e10b68ddbb07e0227d9d56 |
| dist_installer/TaskFlowSetup.exe | 80842175 | ce290b807acf0e4e07c0cbf14a7ffeff6bdaaaeac24930565b6ef71e59f61e2e |

Synthetic verification files are local under build/agent-qa and are ignored. Public screenshots use demo data only. Historical handoff revisions remain in Git; this public document contains no personal workstation paths or process details.

### Use / next action

Close the previous desktop app through the tray Exit action, run the new setup, and bind each project once through the project menu. Install the shared taskflow skill once, then request that project's pending tasks in ordinary language. The copied prompt remains an optional fallback. Real user tasks have not been migrated by test runs. See docs/AGENT_BRIDGE.md for details and rollback limitations.

## Windows CI follow-up

Run 37274333096 passed all 28 tests and built app, agent and installer, then failed when the installer build script printed a Turkish character through the runner's cp1252 console. The success message was changed to ASCII. This changes build logging only; published runtime binaries and verified hashes remain valid. A new clean Windows run is required before claiming CI completion.

### CI closure

Windows run 37274830026 succeeded at source commit 1972606: all 28 tests, agent build, desktop build, installer build and artifact upload passed. The earlier cp1252 logging failure is closed. Public v1.1.0 assets retain the verified local SHA256 digests listed above; the logging-only follow-up does not alter runtime payloads.

## 2026-10-05: shared TaskFlow skill

The user should not have to paste bridge instructions for every project or chat.
skills/taskflow is a shared local Windows skill for natural-language task batches.
Its PowerShell resolver discovers the installed bridge and existing desktop store,
then resolves one exact named project or the current repository's saved binding.
Missing/unmigrated stores, unknown or unbound projects and unavailable repositories
fail without creating another store or guessing a project.

Codex and Claude Code user-scope junctions and thin Codex/Claude/Gemini instruction
routes were installed on the current workstation. Existing global instruction
bytes were preserved, with verified backups. The source and installed skill hashes
match. Gemini uses an instruction pointer, not an unverified native skill catalog.
Local-file discovery does not imply access from cloud sessions.

Verification: all 38 unit/integration tests passed, including 10 new resolver and
bridge-round-trip checks with disposable stores. The skill-creator validator passed.
The existing installed agent resolved a real saved project connection without
claiming tasks. The installed skill and frozen bridge also passed discovery,
list, claim, report and TODO projection checks in a disposable demo profile.
Graphify AST update completed: 303 nodes, 583 edges, 20 communities; no API. No real project tasks were executed during skill installation.
The main application, agent binary and installer payloads are unchanged; no app
reinstall is required. Windows CI now includes the new skill tests; its result for
this change must be recorded separately when available.

Use: after one-time project binding and skill setup, ask the local agent
"TaskFlow'da bekleyen Demo gorevlerini yap". Status-only requests do not execute
tasks. Explicit batches still obey the real repository's instructions, exclusive
claims, evidence requirements and review states. See docs/AGENT_BRIDGE.md.

### Shared skill Windows path follow-up

Windows CI 37282095520 ran all 38 tests: 36 passed and 2 path assertions failed
because the runner's temporary profile used RUNNER~1 while PowerShell returned
the same files under the long profile name. Discovery and bridge execution worked.
Database/repository assertions now verify actual filesystem identity with samefile,
retaining the selected-store checks across Windows short/long path aliases.
A new Windows run is required before claiming CI closure for this change.

### Shared skill CI closure

Windows run 37282414754 succeeded at 24faebb: all 38 tests, bridge/app/installer
builds and artifact upload passed. The short/long path assertion failure is closed.
Latest Graphify AST map has 304 nodes, 584 edges and 20 communities. This closeout
changes documentation only; the tested source and installed skill remain unchanged.

## 2026-10-05: reversible archives and delivery-aware results

Completed tasks now leave the active list through archiving. Archive entries retain
IDs, notes, completion dates, results and report history; restoring returns the
completed task without requeueing it. Project and overflow menus open the archive.
The footer action uses a short label at the minimum window width.

Verified local work is labeled separately from verified publication. Reports accept
local, published or not_applicable delivery scope; new reports default to local.
Legacy task payloads and their unknown delivery scope are preserved. Publication
records require evidence, a current revision and the mapped project/repo, and never
perform deployment. User-review tasks remain unticked even if publication is recorded.
Requeueing resets current delivery scope while retaining its historical evidence.

An additive SQLite event journal retains results across task deletion and project
unbinding. Existing reports are imported once without altering task payloads or
settings. Optional TASKFLOW_HISTORY.md projection preserves manual notes and uses
project UUID markers. The active TODO view excludes archives. Projection errors
preserve the primary data and can be retried without duplicate events. This journal
does not replace repo handoff or private project closeout. Previously deleted results
cannot be recovered. Old app versions do not understand archives; do not use old and
new versions simultaneously with the same store.

Verification:
- All 51 tests passed, including 13 archive/delivery/history regression checks.
- Shared skill validation passed; source and both installed skill junction hashes match.
- The resolver detects delivery support through help, retaining old-bridge compatibility.
- At 440x640 and 340x460 the main content matches the prior revision pixel-for-pixel;
  the intentionally renamed footer action is excluded from that comparison. Archive
  dialog and minimum-width action were visually inspected with synthetic data.
- Frozen application and agent passed the delivery/archive/restore/history lifecycle
  with disposable stores. No real tasks, bindings, startup settings or running app
  were altered. Real-profile installation is not claimed.
- Installer payload hashes match the tested binaries. The actual extracted payloads
  were copied into a disposable installation; shortcut requests were mocked.
- Graphify AST update: 340 nodes, 689 edges, 20 communities; generated output stays
  ignored and no API/LLM was used. Community labels used the deterministic hub fallback.
- Windows CI includes these tests and frozen GUI verification; fresh CI result pending.

Local verified artifacts:
| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| dist_next/TaskFlow.exe | 56301346 | afdaa67f73812873021976592f737dee59a3b5408fc8bf6527f12f54e2c7d311 |
| dist_agent/TaskFlowAgent.exe | 9613019 | 8dca8d9fe5041fb47c1e9f460d5bcf02c37eed59c16fe9266094196ca0f9d43f |
| dist_installer/TaskFlowSetup.exe | 80857684 | df0b6aa748445b4c72807a814890cdd8237ffe3bc447bcb180f0424bae0dcd8c |

Use the new setup after exiting the old app through the tray. Existing local data
and saved project connections are retained. Shared skill updates are already visible
through the installed junctions; the new runtime features require the new setup.
