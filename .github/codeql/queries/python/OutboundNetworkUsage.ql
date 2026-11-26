/**
 * @name Plugin outbound network capability use
 * @description Selected HTTP and socket connection APIs require Dispatcharr's outbound_network capability.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/capability-contract/outbound-network
 * @tags security external/cwe/cwe-269
 */

import python
import semmle.python.ApiGraphs

from API::CallNode call
where
  (
    call = API::moduleImport("requests")
      .getMember(["get", "post", "put", "patch", "delete", "request"]).getACall() or
    call = API::moduleImport("urllib").getMember("request")
      .getMember(["urlopen", "urlretrieve"]).getACall() or
    call = API::moduleImport("socket").getMember("create_connection").getACall() or
    call = API::moduleImport("socket").getMember("socket").getACall().getReturn()
      .getMember(["connect", "connect_ex"]).getACall()
  ) and
  exists(call.getLocation().getFile().getRelativePath())
select call, "This outbound network operation requires the `outbound_network` capability."
