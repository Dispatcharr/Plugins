/**
 * @name Plugin mutation of builtins
 * @description Mutating the plugin's builtins mapping can replace its guarded import or open hooks.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/sandbox-bypass/builtins-mutation
 * @tags security external/cwe/cwe-693
 */

import python

predicate builtinsObject(Expr expression) {
  exists(Name builtins | expression = builtins and builtins.getId() = "__builtins__")
}

from Expr candidate
where
  exists(AssignStmt assignment, Expr target |
    assignment.getATarget() = target and
    (
      exists(Attribute attribute | target = attribute and builtinsObject(attribute.getObject())) or
      exists(Subscript subscript | target = subscript and builtinsObject(subscript.getObject()))
    ) and
    candidate = target
  )
  or
  exists(Call call, Name setattr |
    call.getFunc() = setattr and
    setattr.getId() = "setattr" and
    builtinsObject(call.getArg(0)) and
    candidate = call
  )
select candidate, "Mutating __builtins__ can replace Dispatcharr's plugin-local guarded import or open hooks."
