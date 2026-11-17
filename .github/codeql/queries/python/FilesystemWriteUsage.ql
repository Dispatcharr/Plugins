/**
 * @name Plugin shared directory creation capability use
 * @description Dispatcharr's watched directory creation helper requires the filesystem_write capability.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/capability-contract/filesystem-write
 * @tags security external/cwe/cwe-269
 */

import python

from Call call, Subscript helper, Subscript dispatcharr, StringLiteral helperKey,
  StringLiteral dispatcharrKey, Name context
where
  call.getFunc() = helper and
  helper.getObject() = dispatcharr and
  helper.getIndex() = helperKey and
  helperKey.getText() = "ensure_directory" and
  dispatcharr.getObject() = context and
  context.getId() = "context" and
  dispatcharr.getIndex() = dispatcharrKey and
  dispatcharrKey.getText() = "dispatcharr"
select call, "Creating a watched directory requires the `filesystem_write` capability."
