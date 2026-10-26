/**
 * @name Plugin requests session bypass
 * @description Constructing a requests Session bypasses Dispatcharr's guarded module-level requests helpers.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/sandbox-bypass/requests-session-api
 * @tags security external/cwe/cwe-693
 */

import python
import semmle.python.ApiGraphs

from API::CallNode call
where
  call = API::moduleImport("requests").getMember(["Session", "session"]).getACall()
select call, "Constructing a requests session bypasses Dispatcharr's guarded module-level HTTP helpers."
