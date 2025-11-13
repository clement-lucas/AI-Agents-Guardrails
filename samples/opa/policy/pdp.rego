package pdp

default allow := false
default reason := "No matching policy."
default redactions := []

tool_cfg[t] := data.tool_policies[t]

caller_app_id := input.context.caller_app_id
purpose       := input.context.purpose

deny_tool_by_app { tool_cfg(input.context.tool).deny_apps[_] == caller_app_id }
allow_tool_by_app { tool_cfg(input.context.tool).allow_apps[_] == caller_app_id }

allow {
  input.action == "read_freebusy"
  input.resource.type == "calendar"
  purpose == "meeting_scheduling"
  not deny_tool_by_app
  allow_tool_by_app
}
reason := "Free/busy allowed for meeting scheduling" {
  allow
  input.action == "read_freebusy"
}

allow {
  input.action == "read_project_names"
  input.resource.type == "project_set"
  purpose == "project_collab"
  not deny_tool_by_app
  allow_tool_by_app
}
redactions := ["role_name"] { input.action == "read_project_names" }
