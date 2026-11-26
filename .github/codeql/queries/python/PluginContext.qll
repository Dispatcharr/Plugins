import python
import semmle.python.dataflow.new.DataFlow

/** A helper retrieved from a context parameter, including local aliases. */
predicate contextHelper(Expr helper, string key) {
  exists(Expr context, Name contextName, StringLiteral name |
    contextName.getId() = "context" and
    DataFlow::localFlow(DataFlow::exprNode(contextName), DataFlow::exprNode(context)) and
    name.getText() = key and
    (
      exists(Subscript lookup |
        helper = lookup and lookup.getObject() = context and lookup.getIndex() = name
      )
      or
      exists(Call lookup, Attribute method |
        helper = lookup and lookup.getFunc() = method and method.getName() = "get" and
        method.getObject() = context and lookup.getArg(0) = name
      )
    )
  )
}

predicate contextHelperCall(Call call, string key) {
  exists(Expr helper |
    contextHelper(helper, key) and
    DataFlow::localFlow(DataFlow::exprNode(helper), DataFlow::exprNode(call.getFunc()))
  )
}
