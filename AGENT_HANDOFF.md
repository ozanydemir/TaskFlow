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

Close the previous desktop app through the tray Exit action, run the new setup, and bind each project once through the project menu. Copy the agent prompt when ready to authorize that project's work. Real user tasks have not been migrated by test runs. See docs/AGENT_BRIDGE.md for details and rollback limitations.
