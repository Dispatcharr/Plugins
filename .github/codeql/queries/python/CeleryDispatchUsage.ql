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

from Call call, Subscript helper, StringLiteral key, Name context
where
  call.getFunc() = helper and
  helper.getObject() = context and
  context.getId() = "context" and
  helper.getIndex() = key and
  key.getText() = "dispatch_internal_task"
select call, "This internal task dispatch requires the `celery_dispatch` capability."
