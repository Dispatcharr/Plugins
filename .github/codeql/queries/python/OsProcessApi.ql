/**
 * @name Plugin OS process API bypass
 * @description Direct os process APIs bypass Dispatcharr's guarded subprocess module.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/sandbox-bypass/os-process-api
 * @tags security external/cwe/cwe-693
 */

import python
import semmle.python.ApiGraphs

from API::CallNode call
where
  call = API::moduleImport("os")
    .getMember(["system", "popen", "execv", "execve", "spawnv", "spawnve"]).getACall()
select call, "This os process API bypasses Dispatcharr's guarded subprocess module."
