# Serial-number ordering fix — 24 October 2026

Required correction: the hosted shipment list previously sorted by creation timestamp and UUID. Imported records shared their creation time, so they did not appear in workbook serial order.

Changed `app/shipments/service.py`, `list_shipments()`: numeric serial values sort ascending before pagination. Numeric text such as 2 and 10 now sorts numerically. Nonnumeric serials follow numeric values, with blank/missing serials last. Equal serial labels use original workbook row, then creation time and UUID as stable tie-breakers. Search results and the shipment selector share this ordering. Records are neither renumbered nor merged. No data import or database migration is needed.

# Shipment operations update — 21 October 2026

## Scope and status

Implemented in this patch; not yet installed or deployed to the company environment. User selected SHIPMENT SHEET only and retired the 228-row enquiry dataset. The earlier SQLite migration is superseded and must not be applied for this release. Procurement continues using its existing PostgreSQL data and service behavior.

| File | Change | Why | Necessary? |
|---|---|---|---|
| app/shipments/fields.py | Exact 33-column mapping and date review flags | Preserve workbook meaning without inventing dates | Required |
| app/shipments/store.py | Separate operations tables, UUID, version, source provenance and history | Daily shipment storage without interfering with procurement | Required |
| app/shipments/import_workbook.py | Read only Shipment Sheet; dry-run/default, transactional initial import, exact verification, replay guard | Move the current source safely, keeping duplicate serial rows distinct | Required |
| app/shipments/service.py | Search, create, detail, optimistic update and transactional snapshots | Frontend updates shared by staff without silent lost edits | Required |
| app/shipments/routes.py | Validated token-protected API; unknown fields rejected | Expose controlled read/write actions | Required |
| app/operations_api.py | Combined shipment/procurement entry point | Serve both workflows without importing the retired enquiry database/agent | Required |
| frontend/shipments.py | Count dashboard, all-column table, search, pagination, add/edit forms, review/conflict messages | Staff can maintain daily data from the UI | Required |
| frontend/procurement_hosted.py | Preserve password/session gate; render combined operations UI | Make shipment and procurement workflows available behind existing access control | Required |
| deploy/start.py | Start operations API and validate operations tables | Deploy new UI and backend together; fail clearly before an incomplete setup | Required |
| deploy/requirements.txt | Add openpyxl | Read the initial source workbook | Required for importer |
| tests/check_shipments.py and check_shipments_ui.py | Disposable-DB and UI regression checks | Verify import preservation, shared writes, auth and module coexistence | Required verification |
| install_update.py and manifest.json (package only) | Back up replaced source and install explicit file list | Make replacement and rollback reviewable; never copy secrets/data | Installation helper |

## Material design choices

All 33 business columns are text in this first operational release so partial dates, payment notes, multiple container numbers, mixed sizes and source statuses remain intact. This is deliberate preservation, not a claim of fully normalized date/container models. Future date-based reminders need confirmed typed date fields. No completed/booked statistics are inferred from inconsistent status/remarks.

One cached formula value is imported with the original formula as provenance; a warning remains visible. No AI guess is made. Frontend updates do not recalculate Excel formulas. User edits increment versions; all changed data and its history snapshot commit together. History does not identify individual staff because the retained login is a shared team password.

The hosted navigation is Dashboard / Shipments / Procurement. The old enquiry AI assistant code is retained but not served: its tools refer to the retired schema. Adapting it to shipments is future work. Procurement's existing AI-assisted lane discovery remains available. Transport, mailbox sending, portal automation and commercial features are excluded.

## Verification

Uploaded workbook: 468 nonempty shipment rows; 33 headers match; seven repeated serial occurrences retained; 167 rows with date text needing review; one formula provenance warning. Full import and exact source-value comparison passed in disposable local PGlite. Synthetic API and Streamlit tests passed including create, edit, conflicting edits, history, authentication, unchanged procurement sentinel, and same-source import replay. No real company database writes, cloud deployment, live AI calls or Docker build were performed here. Local Python was 3.12; deployment Docker remains 3.11.

## Previous change history (earlier scope; superseded where noted above)

# Code changes and reasons

Last updated: 17 October 2026
Scope: complete the internal company product first. Commercial subscriptions, multiple-company isolation and billing are deferred.

## How this log is maintained

Each future code update must add: date, files/functions changed, previous and new behavior, reason, necessity (required / optional / temporary), product effect, verification and deployment status. Preserve earlier entries. A prepared patch is not a confirmed live deployment.

This baseline records changes supported by the latest uploaded code, delivered patches and conversation. It is not a reconstruction of every historical Git diff.

## Source baseline and known gaps

- Latest uploaded application: `procurement_current_code(1).zip` (10 October).
- Delivered PostgreSQL procurement patch: `procurement_update.zip`.
- Delivered deployment patch: `render_deployment.zip`.
- Portal investigation helper: `cma_portal_setup.zip`; excluded from the deployed application.
- User confirmed the procurement deployment works. The combined CRM deployment is not complete.
- The archive contains `app/ai/llm.py`, but not `app/ai/agent.py`, `tools.py`, `guardrails.py` or `prompts.py`. None of the other available source archives supplies these modules. They must be preserved from the user's project rather than recreated from assumptions.
- Later safe TLS diagnostic edits were supplied in chat; the downloaded deployment ZIP still contains the original generic exception block. The exact successful Render connection settings have not been supplied. Do not overwrite them with assumed settings.

## Delivered procurement foundation

| Files | Change and reason | Necessary? | Product effect |
|---|---|---|---|
| `app/procurement/pg_database.py` | Procurement engine reads `PROCUREMENT_DATABASE_URL`, with pooling and configurable SSL. | Required for chosen PostgreSQL deployment. | Shared persistent procurement data. |
| `app/procurement/migrate_postgres.py` | Copies existing SQLite reference tables, preserves IDs, compares transferred records, advances sequences and refuses an existing target schema. | Required once for the move to PostgreSQL. | Existing workbook/contact data remains usable. Do not rerun against the migrated schema. |
| `app/procurement/request_tables.py` | Adds stored requests, per-destination plans and enquiry drafts. | Required for saved requests. | Requests survive refreshes and server restarts. |
| `app/procurement/request_schemas.py` | Validates direct shipment input, submission IDs and draft contact selections. | Required. | Procurement can begin without an old CRM enquiry. |
| `app/procurement/request_service.py` | Creates plans per POD; detects duplicate submissions; stores results; rechecks current contact routing before drafting. | Required. | Separate destinations and reusable saved drafts; no automatic sending. |
| `app/procurement/routes.py` | Adds create/list/read request, create draft and email-download endpoints, with optional token checking. | Required. | Frontend can use the saved procurement workflow. |
| `app/procurement/lookup.py` | Reads PostgreSQL reference data; retains port aliases, origin scopes and search-assisted lane fallback; fixes duplicated result handling. | Required. | POD determines candidate lanes without requesting a lane ID. Candidates are not confirmed carrier services. |
| `app/procurement/routing.py` | Reads PostgreSQL contacts while retaining regional office, fallback, agency and equipment rules. | Required. | Booking region controls office selection independently of POL. |
| `app/procurement/manage_contacts.py` | Contact maintenance writes PostgreSQL, handles duplicate contacts and records changes. | Required for current maintenance workflow. | Contact edits reach the data used by procurement. |
| `app/procurement/import_workbook.py`, `import_contact.py`, `match_contact.py`, `discovery_store.py` | Guard legacy SQLite writers when PostgreSQL is configured. | Required to avoid editing a retired copy. | Old commands fail explicitly instead of silently updating unused data. |
| `app/procurement/demo_api.py` | Procurement-only FastAPI entry point and health endpoint. | Temporary delivery choice, not required for the eventual combined product. | Procurement can run without importing the old CRM agent. |
| `frontend/api.py` | Configurable backend URL, timeouts and procurement request/download calls. | Required. | UI communicates with the deployed procurement API. |
| `frontend/procurement.py` | Direct input, saved requests, contact choice and text/email downloads. Corrects treating `error: null` as failure. | Required. | Employees prepare procurement enquiries from new shipment inputs. |
| `frontend/app.py` | Fixes procurement import and includes procurement alongside the CRM tabs. | Required for integration. | Combined interface exists locally; it is not the current hosted entry point. |
| `frontend/procurement_demo.py` | Standalone local procurement page. | Optional development convenience. | Tests procurement separately from the old CRM. |
| Patch installer, restore script and manifest | Back up replaced files and allow code restoration. | Supporting delivery safeguard. | Changes can be applied and reversed without deleting PostgreSQL records. |

Existing `port_resolver.py`, `research_tools.py`, `discovery_schemas.py` and `app/ai/llm.py` supply the search-assisted port classification. They are part of the baseline, not newly authored by the deployment patch.

Verification: earlier backend checks used synthetic data on a local PGlite PostgreSQL engine with external research stubbed. Final UI tests used a mock API. User subsequently confirmed their own migrated procurement workflow was working.

## Delivered Render deployment

| Files | Change and reason | Necessary? | Product effect |
|---|---|---|---|
| `Dockerfile.procurement` | Packages Python code and runs `deploy/start.py` as a non-root user. | Required for the selected Docker approach. | Reproducible application entry point on Render. |
| `Dockerfile.procurement.dockerignore` | Allows application Python and explicit build files; excludes databases, workbooks and local secrets from this image. | Required. | Business data is read from PostgreSQL, not bundled with the image. |
| `deploy/requirements.txt` | Records directly tested deployment dependency versions. | Required; incomplete for the missing CRM agent until its imports are inspected. | Installs the procurement runtime. |
| `deploy/start.py` | Validates configuration/tables, creates an internal API token, starts FastAPI on loopback and Streamlit on the public port, and stops both if either exits. | Required for this single-service design. | One hosted procurement service; startup fails if its required database cannot be read. |
| `frontend/procurement_hosted.py` | Mandatory generated team password, sign-out and eight-hour session expiry before loading procurement content. | Access protection required; shared password is a temporary internal-use choice. | Anonymous visitors cannot load procurement records through this entry point. No individual user audit identity. |
| `render.yaml` | Optional service setup definition using the existing database. | Optional; manual Render setup works too. | Repeatable deployment configuration. |
| `install_deployment.py` | Adds deployment files and backs up existing destination files. | Supporting delivery convenience. | Does not migrate or alter live data. |

Safe connection diagnostics were later expanded in chat to identify common PostgreSQL and TLS failures without printing credentials. Necessary for diagnosis; they do not repair a connection themselves. User confirmed successful deployment afterward; exact final environment values are unknown.

Verification: authentication gating, logout, expiry and unauthorized API checks passed locally. Docker/cloud verification was not performed here; live success was reported by the user.

## Paused portal investigation

`cma_portal_setup/inspect_cma.py` opens a temporary browser for manual login followed by Playwright inspection. It is optional development tooling, not a working rate collector. CMA restricted the helper browser while the user's normal browser worked. Portal automation is explicitly paused. No workaround, booking, mailbox sending or rate extraction was deployed.

## 17 October — documentation added

Files: `docs/CODE_CHANGELOG.md` and `docs/CODE_FLOW_AND_PRODUCT_IMPACT.md`.
Reason: user requested a maintained explanation of code changes, necessity, flow and product effects.
Necessity: required by the user's development workflow; no runtime change.
Verification: file paths checked against available source/patches, missing files identified, current and planned behavior separated.
Deployment: documentation only; no application or live database changes made in this update.

## Next implementation — not yet completed

1. Migrate existing CRM `queries` from SQLite into PostgreSQL with backup, ID preservation, record validation and safe rerun behavior. Do not overwrite procurement tables.
2. Connect `app/database.py` to the intended hosted CRM database while preserving local development support.
3. Start the combined API and all four frontend tabs behind the existing access gate.
4. Inspect the missing CRM AI modules, add their actual dependencies and protect the integrated API routes.
5. Verify CRM records, dashboard statistics, AI tools and procurement together before deploying.

No commercial subscription or multiple-company features are part of this next change.

## 17 October — CRM migration preparation after third source upload

Baseline: `procurement_current_code(2).zip`. It still omits the CRM agent modules and deployment files. Do not interpret the archive version number as evidence that these files were supplied.

| Changed/added file | Why | Necessary? | Product effect |
|---|---|---|---|
| `app/migrate_crm_postgres.py` (new) | Provide a standalone, explicit CRM migration without importing the missing agent or connecting through the old CRM engine. | Required for the approved SQLite-to-PostgreSQL move. | When applied during cutover, copies `queries` into `public.queries`, preserving IDs and existing values. |
| `collect_integration_files.py` (delivery helper) | Collect the specific missing AI/deployment files rather than requesting the full repository again. | Temporary development helper. | No runtime effect. Writes a code archive beside the user's project. |
| Both documentation files | Record the actual patch and separate preparation from completed migration. | Required by user. | Makes migration effects and remaining work reviewable. |

Migration behavior: dry-run is the default; apply requires `--apply`. It takes a consistent SQLite snapshot, validates source columns and boolean values, retains a local backup outside Git on apply, uses a single PostgreSQL transaction, checks complete record equality and advances the ID sequence. An identical target returns without changes; any different existing target is refused. No procurement table is modified. No missing business value is invented.

Scope limitation: this is not the combined application patch. Do not change the live startup or CRM DATABASE_URL yet. Do not apply the data migration while staff continue editing SQLite, as later SQLite changes would not be synchronized.

Verification details are in START_HERE.md. Actual company data and the user's Render deployment have not been accessed. Missing AI/deployment files remain necessary to preserve the original assistant and the successful deployment settings.

Serial-order patch validation: Python syntax compilation passed. No live database or deployment verification performed.
