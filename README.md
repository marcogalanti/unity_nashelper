# unity_nashelper
Helper tool for performing different file storage related functions in Unity XT systems 

During replication NAS servers and relative filesystems could be possible using Proxy NAS feature to access data in the secondary copy of replica, without stopping replication flow: this is almost always a requirement for those systems that are serving in mission critical environments.

To setup such a use case it is necessary to implement a set of steps not always quick to implement as number of NAS servers and share increases.

Unity nas helper is useful to automate the task of creating Proxy NAS server and copy all the shares from the replicates items after creating or reusing existing snapshot of filesystems.
Nashelper also makes easy to list items in the system such as NAS servers, filesystems, shares and snapshot.
It's possible to create snapshot of filesystems
