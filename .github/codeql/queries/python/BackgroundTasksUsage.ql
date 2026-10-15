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

from Call call, Subscript helper, StringLiteral key, Name context
where
  call.getFunc() = helper and
  helper.getObject() = context and
  context.getId() = "context" and
  helper.getIndex() = key and
  key.getText() = "dispatch_task"
select call, "This plugin task dispatch requires the `background_tasks` capability."
