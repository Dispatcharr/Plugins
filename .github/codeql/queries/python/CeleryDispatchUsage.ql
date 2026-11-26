/**
 * @name Plugin internal task dispatch capability use
 * @description Dispatcharr's allowlisted internal-task dispatcher requires the celery_dispatch capability.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/capability-contract/celery-dispatch
 * @tags security external/cwe/cwe-269
 */

import python
import PluginContext

from Call call
where contextHelperCall(call, "dispatch_internal_task")
select call, "This internal task dispatch requires the `celery_dispatch` capability."
