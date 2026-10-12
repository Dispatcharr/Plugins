/**
 * @name Plugin outbound network capability use
 * @description Selected HTTP and socket connection APIs require Dispatcharr's outbound_network capability in enforcing manifests.
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
    call = API::moduleImport("urllib.request").getMember(["urlopen", "urlretrieve"]).getACall()
  )
select call, "This outbound network operation requires the `outbound_network` capability in a runtime-enforcing plugin manifest."
