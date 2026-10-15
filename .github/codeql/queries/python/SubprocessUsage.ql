/**
 * @name Plugin subprocess capability use
 * @description Calling a subprocess API requires Dispatcharr's subprocess capability.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/capability-contract/subprocess
 * @tags security external/cwe/cwe-269
 */

import python
import semmle.python.ApiGraphs
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

predicate dynamicSubprocessCall(Call call) {
  exists(Call importLookup, Name importLookupFunction, Name importlib,
      Call importCall, Call memberLookup, Name memberLookupFunction,
      Expr importMember, Expr moduleName, Expr memberName, Expr importedModule, Expr resolvedMember,
      Expr moduleNameSource, Expr memberNameSource, string moduleValue, string memberValue |
    importLookup.getFunc() = importLookupFunction and
    importLookupFunction.getId() = "getattr" and
    importLookup.getArg(0) = importlib and importlib.getId() = "importlib" and
    importLookup.getArg(1) = importMember and constantString(importMember, "import_module") and
    DataFlow::localFlow(DataFlow::exprNode(importLookup), DataFlow::exprNode(importCall.getFunc())) and
    importCall.getArg(0) = moduleName and
    constantString(moduleNameSource, moduleValue) and
    DataFlow::localFlow(DataFlow::exprNode(moduleNameSource), DataFlow::exprNode(moduleName)) and
    moduleValue = "subprocess" and
    DataFlow::localFlow(DataFlow::exprNode(importCall), DataFlow::exprNode(importedModule)) and
    memberLookup.getFunc() = memberLookupFunction and memberLookupFunction.getId() = "getattr" and
    memberLookup.getArg(0) = importedModule and
    memberLookup.getArg(1) = memberName and
    constantString(memberNameSource, memberValue) and
    DataFlow::localFlow(DataFlow::exprNode(memberNameSource), DataFlow::exprNode(memberName)) and
    memberValue in ["Popen", "run", "call", "check_call", "check_output"] and
    DataFlow::localFlow(DataFlow::exprNode(memberLookup), DataFlow::exprNode(resolvedMember)) and
    call.getFunc() = resolvedMember
  )
}

from Call call
where
  call = API::moduleImport("subprocess")
    .getMember(["Popen", "run", "call", "check_call", "check_output"]).getACall().asExpr()
  or
  dynamicSubprocessCall(call)
select call, "This subprocess call requires the `subprocess` capability."
