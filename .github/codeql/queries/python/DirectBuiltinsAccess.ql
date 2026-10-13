/**
 * @name Plugin direct access to original builtins
 * @description Accessing the global builtins module can bypass the plugin-local open and import wrappers.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/sandbox-bypass/direct-builtins-access
 * @tags security external/cwe/cwe-693
 */

import python
import semmle.python.dataflow.new.DataFlow

predicate constantString(Expr expression, string value) {
  exists(StringLiteral literal |
    expression = literal and value = literal.getText()
  )
  or
  exists(BinaryExpr addition, Expr left, Expr right, string leftValue, string rightValue |
    expression = addition and
    addition.getLeft() = left and
    addition.getRight() = right and
    constantString(left, leftValue) and
    constantString(right, rightValue) and
    value = leftValue + rightValue
  )
}

predicate dynamicBuiltinsAccess(Call access) {
  exists(Call importCall, Name importFunction, Expr moduleName, Expr moduleNameSource,
      Call memberLookup, Name memberLookupFunction, Expr importedModule,
      Expr memberName, Expr memberNameSource, string memberValue |
    importCall.getFunc() = importFunction and importFunction.getId() = "__import__" and
    importCall.getArg(0) = moduleName and
    constantString(moduleNameSource, "builtins") and
    DataFlow::localFlow(DataFlow::exprNode(moduleNameSource), DataFlow::exprNode(moduleName)) and
    memberLookup.getFunc() = memberLookupFunction and memberLookupFunction.getId() = "getattr" and
    memberLookup.getArg(0) = importedModule and
    DataFlow::localFlow(DataFlow::exprNode(importCall), DataFlow::exprNode(importedModule)) and
    memberLookup.getArg(1) = memberName and
    constantString(memberNameSource, memberValue) and
    DataFlow::localFlow(DataFlow::exprNode(memberNameSource), DataFlow::exprNode(memberName)) and
    memberValue in ["open", "__import__"] and
    access = memberLookup
  )
}

from Call call
where
  (
    exists(Attribute function, Name mod |
      call.getFunc() = function and
      function.getObject() = mod and
      mod.getId() = "builtins" and
      function.getName() in ["open", "__import__"]
    )
    or
    dynamicBuiltinsAccess(call)
  )
select call, "Accessing the original builtins module bypasses Dispatcharr's plugin-local wrappers."
