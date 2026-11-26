context["dispatch_internal_task"]("apps.epg.tasks.refresh")
context.get("dispatch_internal_task")("refresh")
dispatch = context["dispatch_internal_task"]
dispatch("refresh")
