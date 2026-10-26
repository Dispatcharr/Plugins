/**
 * @name Plugin importlib access to wrapped module
 * @description Loading a guarded module through importlib bypasses the plugin-local import wrapper.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/sandbox-bypass/importlib-wrapped-module
 * @tags security external/cwe/cwe-693
 */

import python
import semmle.python.ApiGraphs

predicate wrappedModuleName(Expr expression) {
  exists(StringLiteral literal |
    expression = literal and
    literal.getText() in ["subprocess", "socket", "requests", "urllib.request"]
  )
}

from API::CallNode call
where
  call = API::moduleImport("importlib").getMember("import_module").getACall() and
  wrappedModuleName(call.getArg(0).asExpr())
select call, "Loading this module through importlib bypasses Dispatcharr's plugin-local import wrapper."
