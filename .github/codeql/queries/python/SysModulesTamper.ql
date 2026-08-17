/**
 * @name Plugin tampering with sys.modules
 * @description Changing sys.modules can replace or remove sandbox-wrapped modules.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/sandbox-bypass/sys-modules-tamper
 * @tags security external/cwe/cwe-693
 */

import python

predicate sensitiveModuleName(Expr expression) {
  exists(StringLiteral literal |
    expression = literal and
    literal.getText() in ["subprocess", "socket", "os", "urllib.request", "requests",
      "apps.plugins", "apps.plugins.sandbox"]
  )
}

predicate sysModules(Attribute attribute) {
  exists(Name sys |
    attribute.getObject() = sys and sys.getId() = "sys" and attribute.getName() = "modules"
  )
}

from Expr result
where
  exists(AssignStmt assignment, Subscript target, Attribute modules |
    assignment.getTarget() = target and
    target.getObject() = modules and
    sysModules(modules) and
    sensitiveModuleName(target.getIndex()) and
    result = target
  )
  or
  exists(Call call, Attribute pop, Attribute modules |
    call.getFunc() = pop and
    pop.getName() = "pop" and
    pop.getObject() = modules and
    sysModules(modules) and
    sensitiveModuleName(call.getArg(0)) and
    result = call
  )
select result, "Changing this sys.modules entry can bypass sandbox-wrapped imports."
