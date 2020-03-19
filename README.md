# unity_nashelper
# Helper tool for performing different file storage related functions in Unity XT systems 

The main function for which reason this program was created is the NAS storage disaster recovery automation of Unity systems using Proxy NAS server feature. During replication NAS servers and relative filesystems it's possible to test access to the secondary copy using a feature to access data in the secondary copy of the replica, without stopping replication flow: this is almost always a requirement for those storage systems serving in mission critical environments.

To setup such a use case it is necessary to implement a set of command that can consume an import amount of time and effort as number of NAS servers, file systems and share increases.

Unity nas helper is useful to automate the task of creating Proxy NAS server and copy all the shares from the replicates file system after creating or reusing existing snapshot of replicated file systems.
This helper also makes easy to list items such as NAS servers, filesystems, shares and snapshots.
_unity_nashelper_ allows storage admin to create snapshots of filesystems.

![](https://my.one.dell.com/personal/galanm/Documents/ProxyNAS.GIF)

# Setup

In order to run python scripts in _Unity_ console service account logged in have to perform the following steps:

- disable restricted shell via uemcli (by default is enabled)
 
 _uemcli -silent /sys/security set -restrictedShellEnabled no_
 
after issuing this command users have to re-login to the service console start using the unrestricted shell.

- cache admin credential so that password is not requested during step execution for tasks automation.

_uemcli -u admin -securePassword -saveUser_

Once these preparation steps are completed it's possible to run the script:

# Usage


    to automate creation of Unity XT NAS disaster recovery testing env:
    ./unity_nashelper.py --testDR -nas NASserverName

    to show Proxy NAS share(s) info:
    ./unity_nashelper.py --showPROXYSHARE NASserverName

    to show Proxy NAS info:
    ./unity_nashelper.py --showPROXY NASserverName

    to create a filesystem snapshot:
    ./unity_nashelper.py --snap Filesystem <snap name>

    to show NAS server(s) info:
    ./unity_nashelper.py --showNAS NASserverName

    to show file system(s) info:
    ./unity_nashelper.py --showFS <filesystem name>

    to show snapshot(s) info:
    ./unity_nashelper.py --showSNAP <snap name>

    to show share(s) info:
    ./unity_nashelper.py --showSHARE <share name>

    to show filesystem of a NAS server:
    ./unity_nashelper.py --showNASFS NASserverName

    to show a single NAS server share(s) info:
    ./unity_nashelper.py --showNASSHARE <share name>

    add --debug switch to see verbose output
