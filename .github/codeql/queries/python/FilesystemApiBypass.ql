/**
 * @name Plugin direct filesystem API bypass
 * @description Direct filesystem APIs bypass Dispatcharr's plugin-local builtins.open wrapper.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/sandbox-bypass/filesystem-api
 * @tags security external/cwe/cwe-693
 */

import python
import semmle.python.ApiGraphs

/** A directly referenced, non-writing os.open flag. */
predicate safeOpenFlag(Expr flag) {
  flag = API::moduleImport("os")
      .getMember(["O_RDONLY", "O_DIRECTORY", "O_CLOEXEC", "O_NOFOLLOW"])
      .asSource().asExpr()
  or
  exists(BinaryExpr combination |
    flag = combination and combination.getOp() instanceof BitOr and
    safeOpenFlag(combination.getLeft()) and safeOpenFlag(combination.getRight())
  )
}

/** Require an explicit O_RDONLY, not just a combination of auxiliary flags. */
predicate containsReadOnlyFlag(Expr flag) {
  flag = API::moduleImport("os").getMember("O_RDONLY").asSource().asExpr()
  or
  exists(BinaryExpr combination |
    flag = combination and combination.getOp() instanceof BitOr and
    (containsReadOnlyFlag(combination.getLeft()) or containsReadOnlyFlag(combination.getRight()))
  )
}

predicate readOnlyOsOpen(API::CallNode call) {
  exists(Expr flags |
    (flags = call.getArg(1).asExpr() or flags = call.getArgByName("flags").asExpr()) and
    safeOpenFlag(flags) and containsReadOnlyFlag(flags)
  )
}

from API::CallNode call
where
  (
    call = API::moduleImport("io").getMember("open").getACall() or
    call = API::moduleImport("os").getMember("open").getACall() and
      not readOnlyOsOpen(call) or
    call = API::moduleImport("pathlib").getMember("Path").getACall().getReturn()
      .getMember(["open", "write_text", "write_bytes"])
      .getACall()
  )
select call, "This direct filesystem API bypasses Dispatcharr's plugin-local open wrapper."
