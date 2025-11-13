# Secure Data Sharing Between AI Agents — Samples & Quickstart

This repo accompanies the blog post in `blog/secure-agent-data-sharing.md`. It contains runnable snippets for three enforcement patterns (OPA, APIM, MCP) plus a Semantic Kernel client, and now a simple **Azure Functions PEP (Python)** that queries OPA.

## Structure
```
blog/                                  # Full article (Markdown)
diagram/                               # Architecture diagram
samples/
  opa/policy/                          # Rego + policy data
  apim/policies/                       # APIM inbound XML policies
  mcp-server/src/                      # Minimal HTTP PEP server (Node/TS)
  sk-csharp/                           # Semantic Kernel C# sample
  functions-pep/                       # NEW: Azure Functions PEP (Python) querying OPA
```

---

# How to Implement Each Pattern (Step-by-Step)

## Pattern A — OPA (Rego) + Azure Functions (PEP + PDP)

### Prereqs
- Azure CLI, Functions Core Tools, Python 3.10+
- OPA CLI (`brew install opa` or download from opa.dev)
- Entra app registrations for:
  - **Caller Agent** (client credentials for machine-to-machine)
  - **Function App** (audience for `validate-jwt` if APIM fronting it)
- (Optional) Microsoft Graph delegated flow if you’ll do OBO for user data

### 1) Clone the samples and open the folder
```
samples/
  opa/policy/               # Rego + data.json
  functions-pep/            # Azure Functions (Python) PEP that calls OPA
```

### 2) Start OPA with your policy
```bash
cd samples/opa/policy
# Edit data.json allowlists to your app IDs
opa run --server --addr :8181 pdp.rego data.json
```
Health check:
```bash
curl -s localhost:8181/v1/data/pdp -d '{"input":{}}' -H "Content-Type: application/json"
```

### 3) Run the Functions PEP locally
```bash
cd ../../functions-pep
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Copy local.settings.json.example to local.settings.json if needed
func start
```

### 4) Exercise the endpoints (purpose-bound)
```bash
# Calendar free/busy
curl -s -X POST http://localhost:7071/api/calendar_freebusy   -H "Authorization: Bearer <CALLER_APP_JWT>"   -H "x-purpose: meeting_scheduling"   -H "Content-Type: application/json"   -d '{"caller_oid":"1111","range_start":"2025-10-01T00:00:00Z","range_end":"2025-10-07T23:59:59Z","user_delegated_jwt":"<USER_B_DELEGATED_JWT>"}'

# Projects (names only)
curl -s -X POST http://localhost:7071/api/project_info_share   -H "Authorization: Bearer <CALLER_APP_JWT>"   -H "x-purpose: project_collab"   -H "Content-Type: application/json"   -d '{"caller_oid":"1111","user_delegated_jwt":"<USER_B_DELEGATED_JWT>","include_roles":false}'
```

### 5) Wire ABAC/minimization (where to add)
- **ABAC (project intersection):** in `project_info_share/__init__.py` after OPA allow → intersect caller & target memberships (via SQL/Graph) and **only return shared project names**.
- **Minimization:** calendar returns only `(start,end)`; don’t include subjects/locations/attendees unless a separate policy permits it.

### 6) (Optional) Add JWKS validation in the Function
- Use `pyjwt[jwks-client]` or validate via APIM (recommended) and pass along `X-Caller-AppId`.

### 7) Deploy to Azure (minimal)
```bash
# From repo root
az group create -n rg-agent-guardrails -l japaneast
az storage account create -n <storacct> -g rg-agent-guardrails -l japaneast --sku Standard_LRS
func azure functionapp publish <func-app-name> --python
```
Configure app settings: `OPA_URL`, `WEBSITE_RUN_FROM_PACKAGE=1`. Keep OPA reachable (private vnet or containerized next to the Function).

---

## Pattern B — Azure API Management (APIM-only, OPA-free)

### Prereqs
- APIM instance, Function backend (or any HTTP backend)
- Entra app registrations for callers and the API audience

### 1) Import your backend into APIM
- Create an API (HTTP or OpenAPI import) pointing at your Function (or other service).

### 2) Add inbound policies
Open `samples/apim/policies/`:
- `calendar_policy.xml` → apply to the **calendar** operation
- `projects_policy.xml` → apply to the **projects** operation

Set Named Values / policy variables:
- `AAD_OPENID_CONFIG` → `https://login.microsoftonline.com/<tenant-id>/.well-known/openid-configuration`
- `AUDIENCE` → your API App ID URI (e.g., `api://<func-app-app-id>`)
- `ALLOW_APPS_CALENDAR` → `"\"<APPID1>\",\"<APPID2>\""`
- `ALLOW_APPS_PROJECTS` → `"\"<APPID1>\",\"<APPID2>\""`

### 3) Require `x-purpose`
The policy already enforces:
- `meeting_scheduling` for calendar
- `project_collab` for projects

### 4) Backend must still minimize + ABAC
In your Function (or any backend), **ignore** rich fields. Return only minimally required fields. For projects, intersect membership before returning.

### 5) Test through APIM
```bash
curl -s -X POST https://<apim-host>/calendar/freebusy   -H "Authorization: Bearer <CALLER_APP_JWT>"   -H "x-purpose: meeting_scheduling"   -H "Content-Type: application/json"   -d '{"range_start":"2025-10-01T00:00:00Z","range_end":"2025-10-07T23:59:59Z"}'
```
Expect 403 if app id is not in the allowlist or purpose is missing/wrong.

---

## Pattern C — MCP Server as the PEP (TypeScript)

### Prereqs
- Node 18+, ability to verify tokens (for production add JWKS)
- Entra app registrations for caller agents

### 1) Install and run the MCP server
```bash
cd samples/mcp-server
npm init -y
npm i jsonwebtoken
node src/server.ts
```
Set env (optional):
```bash
export SCHEDULER_APPID="<app-id>"
export PMO_APPID="<app-id>"
```

### 2) Call the MCP PEP
```bash
curl -s -X POST http://localhost:8080   -H "Authorization: Bearer <CALLER_APP_JWT>"   -H "x-purpose: meeting_scheduling"   -H "Content-Type: application/json"   -d '{"tool":"calendar_freebusy","payload":{"range_start":"2025-10-01T00:00:00Z","range_end":"2025-10-07T23:59:59Z"}}'
```
Expect `{ allowed: true, minimized: true }` for allowlisted callers with correct purpose.

### 3) Add ABAC + minimization in handlers
- In `src/services/graph.ts` → implement free/busy with **no subjects/locations**.
- In `src/services/sql.ts` → intersect project memberships; **only return shared names** by default.

### 4) Productionize
- Verify JWTs using JWKS (e.g., `jwks-rsa` library).
- Put behind APIM or an internal gateway; use mTLS or private networking.

---

## Wiring Callers (Semantic Kernel + Azure AI Foundry Agents)

### Semantic Kernel (C#)
1) Import your tool OpenAPI (already in `samples/sk-csharp/agents/personal-agent-tools.openapi.yaml`).
2) Add headers per operation (Authorization + purpose):
```csharp
var execParams = new OpenApiFunctionExecutionParameters {
  HttpClient = http,
  EnableDynamicOperationPayloads = true,
  OperationHeadersFactory = async (opName) => new Dictionary<string,string> {
    ["Authorization"] = $"Bearer {await GetCallerTokenAsync()}",
    ["x-purpose"] = opName == "calendar_freebusy" ? "meeting_scheduling" : "project_collab"
  }
};
await kernel.ImportPluginFromOpenApiAsync("MeshTools","agents/personal-agent-tools.openapi.yaml", execParams);
```
3) Invoke like:
```csharp
var args = new KernelArguments {
  ["caller_oid"] = "<OID>",
  ["purpose"] = "meeting_scheduling",
  ["range_start"] = "2025-10-01T00:00:00Z",
  ["range_end"] = "2025-10-07T23:59:59Z",
  ["user_delegated_jwt"] = "<USER_B_DELEGATED_JWT>"
};
var result = await kernel.InvokeAsync("MeshTools","calendar_freebusy", args);
```

### Azure AI Foundry Agents
- Register your tool as an **HTTP tool** (or OpenAPI tool).
- Configure the agent to always send:
  - `Authorization: Bearer <caller token>` (managed identity or app registration)
  - `x-purpose` according to the skill (e.g., the scheduling skill always sets `meeting_scheduling`)
- If the tool will access user data: attach an **On-Behalf-Of** user delegated token flow inside the tool backend.

---

## Testing & CI Hints

- **Unit tests**: mock PDP responses; assert **deny by default**.
- **Integration tests**: run OPA + Functions/MCP locally; hit endpoints with:
  - allowlisted vs non-allowlisted app IDs
  - correct vs wrong `x-purpose`
- **Exfiltration tests**: try prompts that induce the agent to return titles/locations/roles and assert they are **not present** unless policy allows.
- **Observability**: log `(tool, caller_app_id, caller_oid, purpose, decision, reason, latency)`; export to App Insights/Log Analytics.
- **Rate limiting**: enforce in APIM and/or at PEP (per caller app).

---

## Security Hardening (recap)

- **JWT validation** using tenant JWKS (both caller & user tokens).
- **Private networking** (VNET integration), **Managed Identity**, **Key Vault**.
- **Deny by default**; explicit allowlists per tool.
- **Purpose binding** everywhere (APIM, OPA/MCP, backend).
- **Minimization by default** (design outputs to exclude rich fields).
- **ABAC** checks before returning any entity.
- **Throttling & quotas** per caller app.



## Quickstart: OPA (policy decision point)

1. **Run OPA locally** with policy and data:

```bash
cd samples/opa/policy
opa run --server --addr :8181 .
# or: opa run --server --addr :8181 pdp.rego data.json
```

2. **Test a decision**:

```bash
curl -s -X POST localhost:8181/v1/data/pdp   -H "Content-Type: application/json"   -d @- << 'EOF'
{
  "input": {
    "action": "read_freebusy",
    "resource": {"type":"calendar"},
    "context": {
      "tool": "calendar_freebusy",
      "purpose": "meeting_scheduling",
      "caller_app_id": "<SCHEDULER_AGENT_APP_ID>"
    }
  }
}
EOF
```

Expected response contains `allow: true` and an optional `redactions` array.

---

## Quickstart: Azure API Management (perimeter PEP)

- Import the XML policies from `samples/apim/policies/` to your APIM operation(s).
- Set **named values**/policy properties:
  - `AAD_OPENID_CONFIG` – your tenant OIDC metadata URL
  - `AUDIENCE` – API App ID URI (e.g., `api://<function-app-app-id>`)
  - `ALLOW_APPS_CALENDAR`, `ALLOW_APPS_PROJECTS` – quoted app IDs: `""<APPID1>","<APPID2>""`
- Add a **required header** `x-purpose` for each op (`meeting_scheduling` or `project_collab`).

APIM will validate the caller token, check the allowlist, and forward identity + purpose to your backend.

---

## Quickstart: MCP-style PEP (Node/TS)

```bash
cd samples/mcp-server
npm init -y
npm i jsonwebtoken @types/jsonwebtoken -D
node src/server.ts
# POST http://localhost:8080 with JSON:
#   {"tool":"calendar_freebusy", ...}
# and headers: Authorization: Bearer <caller-jwt>, x-purpose: meeting_scheduling
```

The server enforces **allowlist + purpose** and returns a minimized stub payload.

---

## Quickstart: Semantic Kernel C# sample

```bash
cd samples/sk-csharp
dotnet restore
# Set environment variables:
#   AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT
#   AZURE_TENANT_ID, CALLER_AGENT_CLIENT_ID, CALLER_AGENT_CLIENT_SECRET
#   FUNCTION_AUDIENCE_SCOPE, APIM_BASE_URL, B_USER_DELEGATED_JWT
dotnet run
```

The sample imports the tool OpenAPI and sends **Authorization** + **x-purpose** per operation.

---

## Quickstart: Azure Functions PEP (Python) + OPA

This Function acts as a **Policy Enforcement Point**. It:
- extracts the **caller app** and **purpose** from the request,
- calls OPA for an authorization decision,
- if allowed, performs a **minimized** dummy action (free/busy blocks),
- returns 403 with a reason if denied.

### 1) Create a Python virtual env and install deps
```bash
cd samples/functions-pep
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Run OPA (from the OPA Quickstart above)

### 3) Start the Function host
```bash
func start
```

### 4) Call the endpoint
```bash
curl -s -X POST http://localhost:7071/api/calendar_freebusy   -H "Authorization: Bearer <CALLER_APP_JWT>"   -H "x-purpose: meeting_scheduling"   -H "Content-Type: application/json"   -d '{"caller_oid":"1111...","range_start":"2025-10-01T00:00:00Z","range_end":"2025-10-07T23:59:59Z","user_delegated_jwt":"<USER_B_DELEGATED_JWT>"}'
```

### 5) Project info share
```bash
curl -s -X POST http://localhost:7071/api/project_info_share   -H "Authorization: Bearer <CALLER_APP_JWT>"   -H "x-purpose: project_collab"   -H "Content-Type: application/json"   -d '{"caller_oid":"1111...","user_delegated_jwt":"<USER_B_DELEGATED_JWT>","include_roles":false}'
```

### Configuration
- `OPA_URL` – OPA server base URL (default: `http://localhost:8181`).
- `REDACT_SUBJECTS` – `true`/`false` for additional redaction toggles (demo).
- Tokens are **parsed** to read `appid/azp` but not cryptographically validated in this stub; front with APIM or add JWKS validation for production.


---