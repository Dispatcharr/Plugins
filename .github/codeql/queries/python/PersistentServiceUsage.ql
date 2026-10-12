/**
 * @name Plugin persistent service capability use
 * @description Defining Dispatcharr's leader-acquisition hook requires the persistent_service capability in enforcing manifests.
 * @kind problem
 * @problem.severity warning
 * @precision medium
 * @id plugin/capability-contract/persistent-service
 * @tags security external/cwe/cwe-269
 */

import python

from Function hook
where hook.getName() = "on_leader_acquired"
select hook, "This leader service hook requires the `persistent_service` capability in a runtime-enforcing plugin manifest."
