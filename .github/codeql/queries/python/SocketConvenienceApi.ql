/**
 * @name Plugin socket convenience API bypass
 * @description socket.create_connection bypasses the socket constructor proxy that Dispatcharr guards.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/sandbox-bypass/socket-convenience-api
 * @tags security external/cwe/cwe-693
 */

import python
import semmle.python.ApiGraphs

from API::CallNode call
where
  call = API::moduleImport("socket").getMember("create_connection").getACall()
select call, "socket.create_connection bypasses Dispatcharr's guarded socket constructor."
