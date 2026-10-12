/**
 * @name Plugin direct access to original builtins
 * @description Calling the global builtins module bypasses the plugin-local open and import wrappers.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/sandbox-bypass/direct-builtins-access
 * @tags security external/cwe/cwe-693
 */

import python

from Call call, Attribute function, Name mod
where
  call.getFunc() = function and
  function.getObject() = mod and
  mod.getId() = "builtins" and
  function.getName() in ["open", "__import__"]
select call, "Calling the original builtins module bypasses Dispatcharr's plugin-local wrappers."
