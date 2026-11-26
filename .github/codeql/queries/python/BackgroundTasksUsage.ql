/**
 * @name Plugin background task capability use
 * @description Dispatcharr's plugin context dispatcher requires the background_tasks capability.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/capability-contract/background-tasks
 * @tags security external/cwe/cwe-269
 */

import python
import PluginContext

from Call call
where contextHelperCall(call, "dispatch_task")
select call, "This plugin task dispatch requires the `background_tasks` capability."
