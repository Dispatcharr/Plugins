/**
 * @name Plugin network listener capability use
 * @description Binding or listening on a socket requires Dispatcharr's network_listener capability.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/capability-contract/network-listener
 * @tags security external/cwe/cwe-269
 */

import python

from Call call, Attribute function
where
  call.getFunc() = function and
  function.getName() in ["bind", "listen"]
select call, "This socket listener operation requires the `network_listener` capability."
