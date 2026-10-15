/**
 * @name Plugin asyncio process API bypass
 * @description asyncio subprocess APIs bypass Dispatcharr's guarded subprocess module.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/sandbox-bypass/asyncio-process-api
 * @tags security external/cwe/cwe-693
 */

import python
import semmle.python.ApiGraphs

from API::CallNode call
where
  call = API::moduleImport("asyncio")
    .getMember(["create_subprocess_exec", "create_subprocess_shell"]).getACall()
select call, "This asyncio subprocess API bypasses Dispatcharr's guarded subprocess module."
