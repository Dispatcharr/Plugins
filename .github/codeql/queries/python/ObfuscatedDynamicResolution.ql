/**
 * @name Plugin dynamic code resolution
 * @description Dynamic evaluation can obscure module access that bypasses a plugin sandbox.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/sandbox-bypass/obfuscated-dynamic-resolution
 * @tags security external/cwe/cwe-693
 */

import python

from Call call, Name function
where call.getFunc() = function and
  function.getId() in ["eval", "exec"]
select call, "Dynamic evaluation can obscure an attempted plugin sandbox bypass."
