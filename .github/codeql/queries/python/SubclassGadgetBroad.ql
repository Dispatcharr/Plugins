/**
 * @name Plugin sandbox introspection gadget
 * @description Python introspection attributes can expose classes or globals outside a plugin sandbox.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/sandbox-bypass/subclass-gadget-broad
 * @tags security external/cwe/cwe-693
 */

import python

from Attribute attribute
where attribute.getName() in ["__subclasses__", "__globals__", "__mro__"]
select attribute, "This introspection attribute can be used to escape a Python-level sandbox."
