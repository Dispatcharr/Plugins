/**
 * @name Plugin live proxy internals capability use
 * @description Use of known Dispatcharr live proxy implementation APIs should be disclosed.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id plugin/capability-contract/proxy-internals
 * @tags security external/cwe/cwe-269
 */

import python
import semmle.python.ApiGraphs

from API::CallNode call
where
  call = API::moduleImport("apps").getMember("proxy").getMember(["live_proxy", "ts_proxy"])
    .getMember("services").getMember("channel_service").getMember("ChannelService")
    .getMember("_update_stream_stats_in_db").getACall()
select call, "This use of live proxy internals should declare the `proxy_internals` capability."
