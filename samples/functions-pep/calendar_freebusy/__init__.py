import azure.functions as func
import json, os
from .shared import _caller_app_from_authz, evaluate_policy

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.function_name(name="calendar_freebusy")
@app.route(route="calendar_freebusy", methods=["POST"])
def calendar_freebusy(req: func.HttpRequest) -> func.HttpResponse:
    try:
        authz = req.headers.get("Authorization", "")
        purpose = req.headers.get("x-purpose", "")
        caller_app = _caller_app_from_authz(authz)
        allow, meta = evaluate_policy("calendar_freebusy", purpose, caller_app, "read_freebusy", "calendar")
        if not allow:
            return func.HttpResponse(
                json.dumps({"allowed": False, "reason": meta.get("reason","Denied")}),
                status_code=403,
                mimetype="application/json"
            )
        body = req.get_json()
        # DEMO: minimized free/busy only, no subjects/locations
        freebusy = [
            {"start": body.get("range_start"), "end": body.get("range_end")}  # echo range as a single block for demo
        ]
        return func.HttpResponse(json.dumps({"allowed": True, "freebusy": freebusy}), mimetype="application/json")
    except Exception as ex:
        return func.HttpResponse(json.dumps({"error": str(ex)}), status_code=400, mimetype="application/json")
