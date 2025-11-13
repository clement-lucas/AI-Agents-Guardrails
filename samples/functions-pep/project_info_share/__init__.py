import azure.functions as func
import json, os
from .shared import _caller_app_from_authz, evaluate_policy

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.function_name(name="project_info_share")
@app.route(route="project_info_share", methods=["POST"])
def project_info_share(req: func.HttpRequest) -> func.HttpResponse:
    try:
        authz = req.headers.get("Authorization", "")
        purpose = req.headers.get("x-purpose", "")
        caller_app = _caller_app_from_authz(authz)
        allow, meta = evaluate_policy("project_info_share", purpose, caller_app, "read_project_names", "project_set")
        if not allow:
            return func.HttpResponse(
                json.dumps({"allowed": False, "reason": meta.get("reason","Denied")}),
                status_code=403,
                mimetype="application/json"
            )
        # DEMO: return shared project names only (minimized)
        projects = [{"project_id":"p-123","project_name":"Shared Alpha"}]
        return func.HttpResponse(json.dumps({"allowed": True, "projects": projects}), mimetype="application/json")
    except Exception as ex:
        return func.HttpResponse(json.dumps({"error": str(ex)}), status_code=400, mimetype="application/json")
