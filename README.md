# unity_nashelper
Helper tool for performing different file storage related functions in Unity XT systems 

The main function for which reason this program was created is the NAS storage disaster recovery automation of Unity systems using Proxy NAS server feature. During replication NAS servers and relative filesystems it's possible to test access to the secondary copy using a feature to access data in the secondary copy of the replica, without stopping replication flow: this is almost always a requirement for those storage systems serving in mission critical environments.

To setup such a use case it is necessary to implement a set of command that can consume an import amount of time and effort as number of NAS servers, file systems and share increases.

Unity nas helper is useful to automate the task of creating Proxy NAS server and copy all the shares from the replicates file system after creating or reusing existing snapshot of replicated file systems.
This helper also makes easy to list items such as NAS servers, filesystems, shares and snapshots.
_unity_nashelper_ allows storage admin to create snapshots of filesystems.
