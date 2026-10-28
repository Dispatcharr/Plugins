class Plugin:
    name = "Official Manifest v1 Example"
    version = "1.0.0"
    description = "Dispatcharr-maintained example of manifest version 1."
    author = "Dispatcharr Team"

    def run(self, action, params, context):
        if action != "check_endpoint":
            return {"status": "error", "message": f"Unknown action: {action}"}
        return {
            "status": "ok",
            "message": "Manifest version 1 declares capabilities for approval without runtime enforcement.",
            "endpoint": context["settings"].get("endpoint"),
        }
