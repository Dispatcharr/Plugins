/**
 * @name Plugin writes frame globals or locals
 * @description Writing another frame's globals or locals can spoof a frame-based plugin identity check.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/sandbox-bypass/frame-globals-write
 * @tags security external/cwe/cwe-693
 */

import python

from AssignStmt assignment, Subscript target, Attribute frameNamespace
where assignment.getTarget() = target and
  target.getObject() = frameNamespace and
  frameNamespace.getName() in ["f_globals", "f_locals"]
select target, "Writing frame globals or locals can bypass a frame-based plugin sandbox check."
