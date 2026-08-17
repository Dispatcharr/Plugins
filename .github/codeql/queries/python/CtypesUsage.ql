/**
 * @name Plugin use of ctypes
 * @description Native ctypes access can bypass Python-level plugin sandboxing.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/sandbox-bypass/ctypes-usage
 * @tags security external/cwe/cwe-693
 */

import python

from Import imp
where imp.getAnImportedModuleName() = "ctypes"
select imp, "ctypes can load native code outside the plugin sandbox."
