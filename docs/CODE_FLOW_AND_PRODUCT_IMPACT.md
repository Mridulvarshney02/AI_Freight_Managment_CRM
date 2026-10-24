# Code flow and product impact — 21 October 2026

This patch is implemented and locally tested, not yet deployed. Only Shipment Sheet is in scope.

## Initial source import

```mermaid
flowchart TD
    A["Shipment Sheet"] --> B["Validate 33 headers and preserve cells"]
    B --> C{"Apply requested?"}
    C -->|No| D["Report preview; no writes"]
    C -->|Yes| E{"Target empty or same import?"}
    E -->|Different existing data| F["Refuse import"]
    E -->|Same import| G["No changes"]
    E -->|Empty| H["Insert shipments and history"]
    H --> I{"Exact values match?"}
    I -->|Yes| J["Commit transaction"]
    I -->|No| K["Roll back transaction"]
```

`import_workbook.py` reads only SHIPMENT SHEET. `store.py` uses operations tables through the existing PostgreSQL connection. The original workbook, Transport Sheet, old SQLite enquiries and procurement tables remain unmodified. Duplicate serial numbers receive separate UUIDs. Date text stays text; cached formula values retain provenance. Reimporting a changed workbook is refused once daily records exist.

## Hosted interaction and edits

```mermaid
flowchart TD
    A["Hosted Streamlit login"] --> B{"Password accepted?"}
    B -->|No| C["No business data requests"]
    B -->|Yes| D["Dashboard / Shipments / Procurement"]
    D --> E["Open shipment snapshot"]
    E --> F["Edit fields and Save"]
    F --> G["Token and payload validation"]
    G --> H{"Stored version matches?"}
    H -->|No| I["Conflict; reload before retry"]
    H -->|Yes| J["Update row plus history atomically"]
    J --> K["Refresh table and editor"]
```

`frontend/shipments.py` calls `/shipments`. `routes.py` validates field names and lengths; `service.py` updates only supplied fields using ID plus version. Two editors cannot silently overwrite the same version. All staff see committed changes after their next refresh. There is no live-push notification or background Excel sync.

## Deployment and existing procurement

`deploy/start.py` checks procurement and operations tables, generates the shared internal API token, starts `app.operations_api:app` on loopback, then starts `frontend/procurement_hosted.py` on Render's public port. The existing team login protects the full UI. The combined API retains the existing procurement router and adds the shipment router. Neither old `app.main` nor SQLite is imported into this hosted process.

| Before | After |
|---|---|
| Procurement-only hosted view | Shipment dashboard, search/add/edit, and procurement in one login |
| Daily data maintained outside the deployed app | Initial import followed by edits saved in PostgreSQL |
| Old 228 enquiries proposed for migration | Superseded; 468 operational shipment rows from supplied workbook |
| Serial numbers risk being treated as keys | Internal UUIDs preserve repeated source serials |
| Concurrent edits could overwrite a colleague | Version mismatch produces a conflict message |
| Enquiry AI tools query the retired model | Old assistant excluded from new hosted view; procurement AI unchanged |

## Current limits

Shared password means history is not attributable to named users. Dashboard shows count, not inferred shipment milestones. Source date review remains necessary. New-record retries after network timeout require checking whether the first save succeeded. No transport, export screen, daily Excel synchronization, history browsing, portal automation, external email sending or commercial features are added.

## Previous flow history (earlier scope; superseded where noted above)

# Code flow and product impact

Last updated: 17 October 2026
Status: current confirmed deployment is procurement-only. Combined CRM migration/integration is planned.

## Current hosted request flow

```mermaid
flowchart TD
    A["Render container"] --> B["deploy/start.py"]
    B --> C["Validate environment and PostgreSQL tables"]
    C --> D["Loopback API: demo_api.py"]
    C --> E["Public UI: procurement_hosted.py"]
    E --> F{"Team authenticated?"}
    F -->|No| G["Sign-in screen only"]
    F -->|Yes| H["procurement.py"]
    H --> I["frontend/api.py"]
    I --> D
    D --> J["routes.py"]
    J --> K["request_service.py"]
    K --> L["PostgreSQL procurement schema"]
```

Effect: the hosted app currently displays procurement after sign-in. `frontend/app.py` contains the CRM tabs but is not the hosted entry point. `app/main.py` contains CRM endpoints but is not the API launched by this deployment.

## Procurement planning

```mermaid
flowchart TD
    A["Direct shipment inputs"] --> B["request_schemas.py validates"]
    B --> C["request_service.py saves request"]
    C --> D["lookup.py: each POD"]
    D --> E{"Applicable workbook lane found?"}
    E -->|Yes| F["Workbook carrier candidates"]
    E -->|No| G["port_resolver.py and research_tools.py"]
    G --> H{"Eligible lane resolved?"}
    H -->|Yes| F
    H -->|No| I["Review or unresolved result"]
    F --> J["routing.py: booking region and equipment"]
    J --> K["Save destination plan in PostgreSQL"]
    I --> K
    K --> L["Display saved plan"]
```

The search-assisted fallback determines port geography and selects an eligible existing lane. It does not prove that a shipping line currently serves that POD, confirm transshipment, or retrieve a price. The UI must retain coverage and review flags.

## Draft preparation

```mermaid
flowchart TD
    A["Employee selects a contact"] --> B["POST request drafts endpoint"]
    B --> C["request_service.py checks shipment completeness"]
    C --> D["routing.py rechecks current contact rules"]
    D --> E{"Contact and equipment permitted?"}
    E -->|No| F["Return correction message"]
    E -->|Yes| G["Save draft in PostgreSQL"]
    G --> H["UI offers text and email downloads"]
```

Effect: downloads prepare an enquiry. They do not send mail. Portal-only candidates do not become email enquiries merely because the user selects them.

## Why the CRM is absent from the live app

| Concern | Existing CRM | Current hosted procurement |
|---|---|---|
| Frontend entry | `frontend/app.py`: Dashboard, Freight Queries, AI Assistant, Procurement | `frontend/procurement_hosted.py`: login and Procurement |
| API entry | `app/main.py` | `app/procurement/demo_api.py` |
| Database module | `app/database.py`, configured by `DATABASE_URL` | `app/procurement/pg_database.py`, configured by `PROCUREMENT_DATABASE_URL` |
| Data | Existing local SQLite enquiry records | Migrated PostgreSQL reference data, requests and drafts |
| AI dependencies | `app.ai.agent` and its tools, not included in supplied ZIPs | Search-assisted port resolver and Groq configuration supplied |

Switching only the screen does not supply the missing CRM endpoints, database records or dependencies.

## Planned integration — not current behavior

```mermaid
flowchart TD
    A["Existing SQLite CRM"] --> B["Validated one-time migration"]
    B --> C["PostgreSQL CRM records"]
    D["Hosted sign-in"] --> E["Combined frontend/app.py"]
    E --> F["Combined API"]
    F --> G["CRM CRUD, dashboard and AI tools"]
    F --> H["Procurement routes"]
    G --> C
    H --> I["Existing PostgreSQL procurement data"]
```

| Planned code change | Product behavior after verification |
|---|---|
| CRM migration script | Existing enquiries appear in the hosted CRM with preserved identity. |
| `app/database.py` connection configuration | CRM reads/writes persistent PostgreSQL data. |
| Hosted frontend gate and `frontend/app.py` | All four tabs are available after sign-in. |
| `deploy/start.py` and combined API health check | Launcher starts and monitors the combined application. |
| API authentication and `frontend/api.py` headers | CRM and procurement calls use the same internal access boundary. |
| Dependencies based on actual agent imports | AI Assistant can start and use its intended CRM tools. |

The existing procurement data must be preserved. The CRM migration must validate source/target records and retain the SQLite backup. No migration has been executed by these documentation files.

## Update rule

For each future patch, update the affected flow diagram and add a file-to-product-impact row. Label unimplemented behavior as planned, test-only paths as tests, and user-confirmed live behavior separately from local checks. Add the corresponding reason and necessity assessment to `CODE_CHANGELOG.md`.

## New migration command — prepared, not executed on company data

```mermaid
flowchart TD
    A["Read-only local SQLite connection"] --> B["Consistent snapshot"]
    B --> C["Validate schema, IDs, booleans and required status"]
    C --> D{"Apply requested?"}
    D -->|No| E["Inspect target and report dry run"]
    D -->|Yes| F["Retain SQLite backup outside Git"]
    F --> G{"Existing public.queries?"}
    G -->|Identical| H["No changes"]
    G -->|Different| I["Refuse overwrite"]
    G -->|Absent| J["Create and copy in transaction"]
    J --> K["Compare all records and set ID sequence"]
    K --> L["Commit on success; rollback on failure"]
```

`app/migrate_crm_postgres.py` reads `PROCUREMENT_DATABASE_URL` by default only to select the same PostgreSQL database. It writes the CRM table in `public`, not in the existing `procurement` schema. Its execution does not switch the application from SQLite. That switch belongs to the pending combined application patch.

Operational cutover: stop SQLite edits, run the final migration, switch the verified CRM connection/startup, and check saved enquiries and dashboard counts before resuming edits. The migration is not a continuous sync service.
