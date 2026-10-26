/**
 * @name Plugin direct filesystem API bypass
 * @description Direct filesystem APIs bypass Dispatcharr's plugin-local builtins.open wrapper.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/sandbox-bypass/filesystem-api
 * @tags security external/cwe/cwe-693
 */

import python
import semmle.python.ApiGraphs

from API::CallNode call
where
  (
    call = API::moduleImport("io").getMember("open").getACall() or
    call = API::moduleImport("os").getMember("open").getACall() or
    call = API::moduleImport("shutil")
      .getMember(["copy", "copy2", "copyfile", "copytree", "move", "rmtree"]).getACall() or
    call = API::moduleImport("pathlib").getMember("Path").getACall().getReturn()
      .getMember(["open", "write_text", "write_bytes", "touch", "mkdir", "unlink", "rename", "replace"])
      .getACall()
  )
select call, "This direct filesystem API bypasses Dispatcharr's plugin-local open wrapper."
