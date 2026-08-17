/**
 * @name Plugin mutation of builtins
 * @description Mutating builtins can alter import and identity behavior outside a plugin sandbox.
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

from Expr result
where
  exists(AssignStmt assignment, Expr target |
    assignment.getTarget() = target and
    (
      exists(Attribute attribute | target = attribute and builtinsObject(attribute.getObject())) or
      exists(Subscript subscript | target = subscript and builtinsObject(subscript.getObject()))
    ) and
    result = target
  )
  or
  exists(Call call, Name setattr |
    call.getFunc() = setattr and
    setattr.getId() = "setattr" and
    builtinsObject(call.getArg(0)) and
    result = call
  )
select result, "Mutating __builtins__ can bypass a Python-level plugin sandbox."
