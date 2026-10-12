/**
 * @name Plugin subprocess capability use
 * @description Calling a subprocess API requires Dispatcharr's subprocess capability in enforcing manifests.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/capability-contract/subprocess
 * @tags security external/cwe/cwe-269
 */

import python
import semmle.python.ApiGraphs

from API::CallNode call
where
  call = API::moduleImport("subprocess")
    .getMember(["Popen", "run", "call", "check_call", "check_output"]).getACall()
select call, "This subprocess call requires the `subprocess` capability in a runtime-enforcing plugin manifest."
