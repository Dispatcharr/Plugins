/**
 * @name Plugin subclass enumeration gadget
 * @description Enumerating subclasses is a common Python sandbox escape primitive.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/sandbox-bypass/subclass-gadget-exact
 * @tags security external/cwe/cwe-693
 */

import python

from Call call, Attribute subclasses
where call.getFunc() = subclasses and
  subclasses.getName() = "__subclasses__" and
  (
    subclasses.getObject().(Name).getId() in ["object", "type"]
    or
    exists(Subscript index, Attribute bases, Attribute classAttribute |
      subclasses.getObject() = index and
      index.getObject() = bases and
      bases.getName() in ["__bases__", "__mro__"] and
      bases.getObject() = classAttribute and
      classAttribute.getName() = "__class__"
    )
  )
select call, "Subclass enumeration can expose objects outside the plugin sandbox."
