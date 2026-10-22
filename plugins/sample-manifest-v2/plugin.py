from pathlib import Path


class Plugin:
    name = "Official Manifest v2 Example"
    version = "1.0.0"
    description = "Dispatcharr-maintained example of manifest version 2."
    author = "Dispatcharr Team"

    def run(self, action, params, context):
        if action != "write_status":
            return {"status": "error", "message": f"Unknown action: {action}"}

        message = context["settings"].get("message", "Hello from Dispatcharr")
        status_path = Path(context["data_dir"]) / "status.txt"
        status_path.write_text(message, encoding="utf-8")
        context["report_progress"](100, "Status file written")
        return {"status": "ok", "message": f"Wrote {status_path.name}"}
