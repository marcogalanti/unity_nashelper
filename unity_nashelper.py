#!/usr/bin/python
"""
developed by Marco Galanti (marco.galanti@gmail.com)
create "bubble environment" on Unity for DR testing procedure

This is program is meant to run in the Unity service console

make sure restricted shell is not enabled in Unity, run the following uemcli
uemcli -silent /sys/security set -restrictedShellEnabled no

also, in order to create snap with auth issue make sure user credential
are saved locally (local user can be removed afterward)

[Save access credentials for the destination system locally]
uemcli [-d <address>] [-port <number>] -u <user_name> { -p <password> | -securePassword } [-silent] [-enableStdErr] -saveUser

[Remove access credentials for the destination system from this client]
uemcli [-d <address>] [-port <number>] [-silent] [-enableStdErr] -removeUser

to test NAS DR using Proxy NAS feature following macro steps are automated by this program

1) create new or reuse existing snapshot of replicated NAS filesystem
2) create NAS server and configure as proxy NAS server linked to Replicates NAS server
3) create shares in Proxy NAS server duplicating replicated NAS filesystem share linking snapshot of 1)

"""

from sys import argv
import os
import subprocess
import datetime
import time

d = datetime.datetime.now()

"""
>>> d.today().strftime("%d%b%Y")
'05Mar2020'

"""

script = argv[0]
version = "1.0.1"

debug = 0  # from 0 to 3 to increase output verbosity

# Customization
DRTEST_PROXYNAS_SUFFIX = "_TESTDR"
DRTEST_SNAP_SUFFIX = "_TESTDR_" + d.today().strftime("%d%b%Y")
DRTEST_SNAP_RETENTION = "15d"  # 15 Days of DR Testing Snapshot retention

cli = "/usr/bin/uemcli -silent"
uemcli_user = "admin"
nasServer_show = (cli + " /net/nas/server show -output csv").split()
filesystem_show = (cli + " /stor/prov/fs show -output csv").split()
snapshot_show = (cli + " /prot/snap show -output csv").split()
share_show = (cli + " /stor/prov/fs/cifs show -output csv").split()
pool_show = (cli + " /stor/config/pool show -output csv").split()

# input value of filesystem and nas server, snapshot is fs + DRTEST_SNAP_SUFFIX
fileSystem = ""
share = ""
snapshot = ""
nasServer = ""
pool_id = ""
# list of all fs / nas server / snap / cifs shares from unity system
fileSystems = []
shares = []
snapshots = []
nasServers = []
pools = []


def usage():
    # print help
    # no input
    # no output
    print('''
    Helper for different Unity NAS functions

    Usage
    -----

    to automate creation of Unity XT NAS disaster recovery testing env:
    {} --testDR -nas NASserverName

    to show Proxy NAS share(s) info:
    {} --showPROXYSHARE NASserverName

    to show Proxy NAS info:
    {} --showPROXY NASserverName

    to create a filesystem snapshot:
    {} --snap Filesystem <snap name>

    to show NAS server(s) info:
    {} --showNAS NASserverName

    to show file system(s) info:
    {} --showFS <filesystem name>

    to show snapshot(s) info:
    {} --showSNAP <snap name>

    to show share(s) info:
    {} --showSHARE <share name>

    to show filesystem of a NAS server:
    {} --showNASFS NASserverName

    to show a single NAS server share(s) info:
    {} --showNASSHARE <share name>

    add --debug switch to see verbose output
    '''.format(script, script, script, script, script, script, script, script, script, script))


def about():
        # print about
        # nothing
        # nothing
    print('''
Helper script to make easier some unity tasks
{} version {} (author: Marco Galanti - marco.galanti@gmail.com)
'''.format(script, version))


"""
NAS SERVER
ID,Name,NetBIOS name,SP,Storage pool,Tenant,Interface,NFS enabled,NFSv3 enabled,NFSv4 enabled,CIFS enabled,Multiprotocol sharing enabled,Unix directory service,Health state
"""


class Pool:

    def __init__(self, id, name, totalspace, freespace, subscriptionpercent, numberofdrives, raidlevel, stripelength, rebalancing, health, protectionsize, nonbasesizeused):
        self.id = id.strip('"')
        self.name = name.strip('"')
        self.totalspace = totalspace.split("(")[0][0:-1].strip('"')
        self.freespace = freespace.split("(")[0][0:-1].strip('"')
        self.subscriptionpercent = subscriptionpercent.strip('"')
        self.numberofdrives = numberofdrives.strip('"')
        self.raidlevel = raidlevel.strip('"')
        self.stripelength = stripelength.strip('"')
        self.rebalancing = rebalancing.strip('"')
        self.health = health .strip('"')
        self.protectionsize = protectionsize.split("(")[0][0:-1].strip('"')
        self.nonbasesizeused = nonbasesizeused.split("(")[0][0:-1].strip('"')

    def show(self):
        print("id: {}".format(self.id))
        print("name: {}".format(self.name))
        print("total space: {}".format(self.totalspace))
        print("free space: {}".format(self.freespace))
        print("% subscription: {}".format(self.subscriptionpercent))

    @property
    def condition(self):
        cond = self.health
        return cond


class Nasserver:

    def __init__(self, id, name, netbios, sp, poolname, tenant, interface, nfsEnabled, nfs3Enabled, nfs4Enabled, cifsEnabled, multiprotocol, unixDirectoryService, health):
        self.id = id.strip('"')
        self.name = name.strip('"')
        self.netbios = netbios.strip('"')
        self.sp = sp.strip('"')
        self.poolname = poolname.strip('"')
        self.tenant = tenant.strip('"')
        self.interface = interface.strip('"')
        self.nfsEnabled = nfsEnabled.strip('"')
        self.nfs3Enabled = nfs3Enabled.strip('"')
        self.nfs4Enabled = nfs4Enabled.strip('"')
        self.cifsEnabled = cifsEnabled.strip('"')
        self.multiprotocol = multiprotocol.strip('"')
        self.unixDirectoryService = unixDirectoryService.strip('"')
        self.health = health.strip('"')

    def show(self):
        print("id: {}".format(self.id))
        print("name: {}".format(self.name))
        print("interface: {}".format(self.id))
        print("netbios: {}".format(self.netbios))
        print("health: {}".format(self.health))
        print("cifs enabled: {}".format(self.cifsEnabled))
        print("nfs enabled: {}".format(self.nfsEnabled))
        print("nfs3 enabled: {}".format(self.nfs3Enabled))
        print("nfs4 enabled: {}".format(self.nfs4Enabled))

    @property
    def condition(self):
        cond = self.health
        return cond


"""
CIFS SHARE
ID,Name,Description,File system,Local path,Export path

"""


class Share:

    def __init__(self, id, name, description, filesystem, path, export):
        self.id = id.strip('"')
        self.name = name.strip('"')
        self.description = description.strip('"')
        self.filesystem = filesystem.strip('"')
        self.path = path.strip('"')
        self.export = export.strip('"')

    def show(self):
        print("id: {}".format(self.id))
        print("name: {}".format(self.name))
        print("description: {}".format(self.description))
        print("filesystem: {}".format(self.filesystem))
        print("path: {}".format(self.path))
        print("export: {}".format(self.export))


"""
FILESYSTEM
ID,Name,Description,Health state,File system,Server,Storage pool ID,Storage pool,Format,Protocol,Access policy,Folder rename policy,Locking policy,Size,Size used,Maximum size,Protection size used
"""


class Filesystem:

    def __init__(self, id, name, description, health, filesystem, server, poolid, poolname, format, protocol, accessPolicy, folderRenamePolicy, lockingPolicy, size, sizeused, maxsize, protsizeused):
        self.id = id.strip('"')
        self.name = name.strip('"')
        self.description = description.strip('"')
        self.health = health.strip('"')
        self.filesystem = filesystem.strip('"')
        self.server = server.strip('"')
        self.poolid = poolid.strip('"')
        self.poolname = poolname.strip('"')
        self.format = format.strip('"')
        self.protocol = protocol.strip('"')
        self.accessPolicy = accessPolicy.strip('"')
        self.folderRenamePolicy = folderRenamePolicy.strip('"')
        self.lockingPolicy = lockingPolicy.strip('"')
        self.size = size.split("(")[0][0:-1].strip('"')
        self.sizeused = sizeused.split("(")[0][0:-1].strip('"')
        self.maxsize = maxsize.split("(")[0][0:-1].strip('"')
        self.protsizeused = protsizeused.split("(")[0][0:-1].strip('"')

    def show(self):
        print("id: {}".format(self.id))
        print("name: {}".format(self.name))
        print("server: {}".format(self.server))
        print("protocol: {}".format(self.protocol))
        print("size: {}".format(getHumanReadableSize(self.size)))

    @property
    def condition(self):
        cond = self.health.split("(")[1]
        cond = cond[0:1]
        return cond


"""
SNAPSHOT
ID,Name,State,Attached,Source,Source Type,Members,Attach details
"""


class Snapshot:

    def __init__(self, id, name, state, attached, source, sourcetype, members, attachDetails):
        self.id = id.strip('"')
        self.name = name.strip('"')
        self.state = state.strip('"')
        self.source = source.strip('"')
        self.sourcetype = sourcetype.strip('"')
        self.members = members.strip('"')
        self.attachDetails = attachDetails.strip('"')

    def show(self):
        print("id: {}".format(self.id))
        print("name: {}".format(self.name))
        print("state: {}".format(self.state))
        print("source: {}".format(self.source))
        print("sourcetype: {}".format(self.sourcetype))

    @property
    def condition(self):
        cond = self.state
        return cond


def secondsInHumanReadableTime(seconds):
    # get time expressed in seconds and return time in days, hours, minutes....
    # input -> seconds
        # output -> string reporting input time in human form
    if seconds < 60:  # seconds
        return '{} seconds'.format(seconds)
    if seconds < 3600:  # minutes
        mins = seconds//60
        secs = seconds % 60
        return '{} minutes and {} seconds'.format(mins, secs)
    if seconds < 86400:  # hours
        hours = seconds//3600
        remainder = seconds % 3600
        if remainder > 60:
            mins = remainder//60
            return '{} hours and {} minutes'.format(hours, mins)
        else:
            return '{hours} hours'.format(hours)
    else:  # days
        days = seconds//86400
        remainder = seconds % 86400
        if remainder < 3600:
            return '{} days'.format(days)
        else:
            hours = remainder//3600
            remainder2 = remainder % 3600
            if remainder2 > 60:
                minutes = remainder2//60
                return '{} days, {} hours and {} minutes'.format(days, hours, minutes)
            else:
                return '{} days and {} hours'.format(days, hours)


def getHumanReadableDateTime(timestamp):
    return time.ctime(timestamp)


def getHumanReadableSize(size):
        # print a storage capacity from 1k block in humanreadable format
    size = int(size)
    if size < 2**10:  # byte
        return "%s bytes" % round(size, 2)
    elif size < 2**20:  # kibibyte
        v = size / (2**10)
        return "%sKiB" % round(v, 2)
    elif size < 2**30:  # mebibyte
        v = size / (2**20)
        return "%sMiB" % round(v, 2)
    elif size < 2**40:  # gibibyte
        v = size / (2**30)
        return "%sGiB" % round(v, 2)
    elif size < 2**50:  # tebibyte
        v = size / (2**40)
        return "%sTiB" % round(v, 2)
    else:  # pebibyte
        v = size / (2**50)
        return "%sPiB" % round(v, 2)


def setMachineReadableSize(size, unit):
        # convert a humanreadable capacity storage format into a 1k block storage capacity
    if unit == "MiB":
        size = int(size)*1024*1024
    elif unit == "GiB":
        size = int(size)*1024*1024*1024
    elif unit == "TiB":
        size = int(size)*1024*1024*1024*1024
    else:
        flash('cannot get filesystem size chosen, please retry', 'danger')
    return size


def valueInMB(capacity):
        # get input like 10.0GiB and returns 10240 (equivalent value in MB)
    # <-- this gets last 3 letters (KiB / MiB / GiB / TiB / PiB)
    unit = capacity[:-3]
    sizeInMB = float(capacity[0:-3])
    if unit == 'KiB':
        return sizeInMB / 1024
    elif unit == 'MiB':
        return sizeInMB
    elif unit == 'GiB':
        return sizeInMB * 1024
    elif unit == 'TiB':
        return sizeInMB * (1024*1024)
    elif unit == 'PiB':
        return sizeInMB * (1024*1024*1024)
    else:  # value is in byte
        return sizeInMB / (1024*1024)


def dbg(obj, private="public"):
    # print object class and all attributes
        # input -> object to inspect
    # output -> print to screen object method and attributes
    # (also private if passed string "private" as argument)
    import inspect
    class_name = obj.__class__.__name__
    print("Class: %s" % (class_name))
    members = inspect.getmembers(obj)
    for m in members:
        if private == "private" or not((m[0][0:2] == "__") and (m[0][-2:-1] == "_")):
            print(m)


def getattrs(obj):
        # print class and attributes of a dictionary
        # input -> dictionary
    # output -> print to screen dictionary class and keys
    print("ATTR \'%s\'->%r" % (obj.__class__.__name__, obj.__dict__.keys()))


def cmdParser():
    # parse command arguments and start program function according to arguments
    global filesystem
    global nasServer
    global debug
    function_name = ""
    if len(argv) == 1:
        return False
    else:
        command = argv.pop(0)
    evaluated_args = []
    while len(argv) > 0:
        if ("--help" in argv) or ("-h" in argv) or ("-?" in argv):
            evaluated_args.append("--help")
            return False
        if "--debug" in argv:
            argv.remove("--debug")
            debug = 1
        singlearglist = ["--showNASFS"
                         "--showPROXYSHARE",
                         "--showPROXY",
                         "--showNASSHARE",
                         "--showNASFS",
                         "--showSNAP",
                         "--showFS",
                         "--showNAS",
                         "--showSHARE"]
        for arg in singlearglist:
            if arg in argv:
                func = globals()[arg[2:]]
                print(function_name)
                evaluated_args.append(arg)
                argv.remove(arg)
                if debug > 0:
                    print("evaluated args {}".format(evaluated_args))
                if len(argv) == 1:
                    func(argv[0])
                elif len(argv) == 0:
                    func()
                else:
                    print("wrong arguments")
                exit()
        if ("--SNAP" in argv) or ("--snap" in argv):
            if ("--SNAP" in argv):
                argv.remove("--SNAP")
            else:
                argv.remove("--snap")
            evaluated_args.append("--snap")
            if len(argv) == 1:  # if only one arg is provided then filesystem to snap is the argument
                createFsSnap(argv[0], "")
            # if two args are provided then filesystem to snap and snapshot name are the arguments
            elif len(argv) == 2:
                createFsSnap(argv[0], argv[1])
            else:
                print("wrong arguments!")
                usage()
            exit()
        elif ("--testDR" in argv):
            evaluated_args.append("--testDR")
            argv.remove("--testDR")
            # if 2 arguments are available in the arg list then must be "--nasserver","nas name"
            if (len(argv) == 2) and ("-nas" in argv):
                argv.remove("-nas")
                evaluated_args.append("-nas")
                evaluated_args.append(argv[0])
                nasServer = argv[0]
                argv.remove(argv[0])
                return True
        else:
            print("\nWrong arguments specified in the command !")
            return False
    return False


def getSnaps():
    # create snap objects from all snapshot in unity by executing uemcli
    global snapshot_show
    if debug > 0:
        print("calling getSnaps()")
    snaplist = []
    output = subprocess.check_output(snapshot_show)
    for snapline in output.splitlines()[1:]:
        if debug > 1:
            print("-debug1- print snap csv list getSnaps() --")
            print(snapline.split(","))
        id, name, state, attached, source, sourcetype, members, attachDetails = snapline.split(
            ",")
        snap = Snapshot(id, name, state, attached, source,
                        sourcetype, members, attachDetails)
        snaplist.append(snap)
    return snaplist


def getShares():
    # create shares objects from all filesystem in unity by executing uemcli
    global share_show
    if debug > 0:
        print("calling getShares()")
    sharelist = []
    output = subprocess.check_output(share_show)
    for shareline in output.splitlines()[1:]:
        if debug > 1:
            print("-- print share csv list getShares() --")
            print(shareline.split(","))
        id, name, description, filesystem, path, export = shareline.split(",")[
            0: 6]
        share = Share(id, name, description, filesystem, path, export)
        sharelist.append(share)
    return sharelist


def getPools():
    # create pools objects from unity system by executing uemcli
    global pool_show
    if debug > 0:
        print("calling getPools()")
    poollist = []
    output = subprocess.check_output(pool_show)
    for poolline in output.splitlines()[1:]:
        if debug > 2:
            print("-- print pool csv list getPools() --")
            print(poolline)
        id, name, totalspace, freespace, subscriptionpercent, numberofdrives, raidlevel, stripelength, rebalancing, health, protectionsize, nonbasesizeused = poolline.split(
            ",")
        pool = Pool(id, name, totalspace, freespace, subscriptionpercent, numberofdrives,
                    raidlevel, stripelength, rebalancing, health, protectionsize, nonbasesizeused)
        poollist.append(pool)
    return poollist


def getFilesystems():
    # create Filesystem objects from all filesystem in unity by executing uemcli
    global filesystem_show
    if debug > 0:
        print("calling getFilesystems()")
    fslist = []
    output = subprocess.check_output(filesystem_show)
    for fsline in output.splitlines()[1:]:
        if debug > 2:
            print("-- print filesystem csv list getFilesystems() --")
            print(fsline)
        id, name, description, health, fs, server, poolid, poolname, format, protocol, accessPolicy, folderRenamePolicy, lockingPolicy, size, sizeused, maxsize, protsizeused = fsline.split(
            ",")
        fs = Filesystem(id, name, description, health, fs, server, poolid, poolname, format, protocol,
                        accessPolicy, folderRenamePolicy, lockingPolicy, size, sizeused, maxsize, protsizeused)
        fslist.append(fs)
    return fslist


def getFSnames():
    if debug > 0:
        print("calling getFSnames()")
    fsNameList = []
    for fs in fileSystems:
        fsNameList.append(fs.name)
    return fsNameList


def getFSbyName(name):
    # return Filesystem object from a query by name of Filesystem obj list
    # if not found return None
    if debug > 0:
        print("calling getFSbyName()".format(name))
    for fs in fileSystems:
        if name == fs.name:
            return fs
    return None


def getSnapshots():
    # create Snapshot objects from all snapshot in unity by executing uemcli
    global snapshot_show
    if debug > 0:
        print("calling getSnapshots()")
    snaplist = []
    output = subprocess.check_output(snapshot_show)
    for snapline in output.splitlines()[1:]:
        if debug > 2:
            print("-- print snap csv list getSnapshots() --")
            print(snapline)
        id, name, state, attached, source, sourceType, members, attachDetails = snapline.split(
            ",")
        snap = Snapshot(id, name, state, attached, source,
                        sourceType, members, attachDetails)
        snaplist.append(snap)
    return snaplist


def getNASservers():
    # create Nasserver objects from all nas server in unity by executing uemcli
    global nasServer_show
    if debug > 0:
        print("calling getNASservers()")
    naslist = []
    output = subprocess.check_output(nasServer_show)
    for nasline in output.splitlines()[1:]:
        if debug > 2:
            print("-- print nas server csv list getNASservers() --")
            print(nasline)
        id, name, netbios, sp, poolname, tenant, interface, nfsEnabled, nfs3Enabled, nfs4Enabled, cifsEnabled, multiprotocol, unixDirectoryService, health = nasline.split(
            ",")
        nas = Nasserver(id, name, netbios, sp, poolname, tenant, interface, nfsEnabled,
                        nfs3Enabled, nfs4Enabled, cifsEnabled, multiprotocol, unixDirectoryService, health)
        naslist.append(nas)
    return naslist


def getNASnames():
    # return Nasserver name list from nas server obj list
    if debug > 0:
        print("calling getNASnames()")
    NASNameList = []
    for nas in nasServers:
        NASNameList.append(nas.name)
    return NASNameList


def getSharebyName(name):
        # get a NAS share from a queries name
        # input -> name of a share
        # output -> sha object
    global shares
    if len(shares) == 0:
        shares = getShares()
    # return Nasserver object from a query by name of nas server obj list
    # if not found return None
    if debug > 0:
        print("calling getSharebyName({})".format(name))
    for share in shares:
        if name == share.name:
            return share
    return None


def getNASbyName(name):
        # return a nas object from a queries name
        # input -> name (string)
        # output -> nas object
    global nasServers
    if len(nasServers) == 0:
        nasServers = getnasServers()
    # return Nasserver object from a query by name of nas server obj list
    # if not found return None
    if debug > 0:
        print("calling getNASbyName({})".format(name))
    for nas in nasServers:
        if name == nas.name:
            return nas
    return None


def getNASbyID(ID):
    # return Nasserver object from a query by ID of nas server obj list
        # input -> nas id (string)
        # output -> nas object
    if debug > 0:
        print("calling getNASbyID({})".format(ID))
    for nas in nasServers:
        print(nas.id)
        if ID == nas.id:
            return nas
    return None


def getFSbyID(ID):
    # return filesystem object from a query by ID of filesystem obj list
        # input -> filesystem id (string)
        # output -> filesystem object
    global fileSystems
    if debug > 0:
        print("calling getFSbyID({})".format(ID))
    for fs in fileSystems:
        if ID == fs.id:
            return fs
    return None


def printNASlist():
    # print name of all nas server from a list of Nasserver objects
    global nasServers
    if debug > 0:
        print("calling printNASlist()")
    if len(nasServers) > 0:
        for nas in nasServers:
            print(nas.name)


def printFSlist():
    # print name of all filesystem from a list of Filesystem objects
    global fileSystems
    if debug > 0:
        print("calling printFSlist()")
    if len(fileSystems) > 0:
        for fs in fileSystems:
            print(fs.name)


def getFSidsByNasID(NASid):
    # return a list of filesystem ids associated to a queries NAS Server id
    # input -> nas server id
    # output -> a list of file system id
    global fileSystems
    filesystem_ids = []
    for fs in fileSystems:
        if fs.server == NASid:
            filesystem_ids.append(fs.id)
    return filesystem_ids


def getNASidByName(name):
    # return an id of nas server ids associated to a queries NAS Server id
    # input -> nas server id
    # output -> nas server id
    global nasServers
    for nas in nasServers:
        if nas.name == name:
            return nas.id


def showNASFS(name=None):
    # show list of filesystem with details of a given nas server name passed as name argument
        # input -> nas server name (if no input all share will be printed)
        # output -> print only (no return)
    global shares
    global nasServers
    global fileSystems
    outlist = []
    if debug > 0:
        print("calling showNASFS({})".format(name))
    nasServers = getNASservers()
    if name and nas != "":
        NASid = getNASidByName(name)
        if NASid:
            fileSystems = getFilesystems()
            fileSystem_ids = []
            fileSystem_ids = getFSidsByNasID(NASid)
            if len(fileSystems) > 0:
                for fs in fileSystems:
                    if fs.server == NASid:
                        print("NAS: ({}) fs: ({})".format(name, fs.name))
            else:
                print("no file system present".format(name))
        else:
            print("NAS server ({}) not found! ".format(name))
    else:
        print("Please specify a valid NAS server in the command!")
    exit()


def showNASSHARE(name=None):
    # show list of share with details of a given nas server name passed as name argument
        # input -> nas server name (if no input all share will be printed)
        # output -> print only (no return)
    global shares
    global nasServers
    global fileSystems
    if debug > 0:
        print("calling showNASSHARE({})".format(name))
    nasServers = getNASservers()
    nas = getNASbyName(name)
    if nas:
        shares = getShares()
        fileSystems = getFilesystems()
        NASid = getNASidByName(name)
        fileSystem_ids = []
        fileSystem_ids = getFSidsByNasID(NASid)
        if len(shares) > 0:
            for share in shares:
                if share.filesystem in fileSystem_ids:
                    fs = getFSbyID(share.filesystem)
                    print("NAS: ({}) share: ({}) fs: ({}) path: ({}) export: ({})".format(
                        name, share.name, fs.name, share.path, share.export))
        else:
            print("no share present in nas server ()".format(name))
    else:
        if name == None:
            print("Please specify a valid NAS server in the command!")
        else:
            print("NAS server ({}) not found! ".format(name))
    exit()


def showSHARE(name=None):
    # show share detail (all share are displayed if no name arg is passed)
        # input -> share name (if no input all share will be printed)
        # output -> print only (no return)
    global shares
    shares = getShares()
    if len(shares) > 0:
        if debug > 0:
            print("calling showSHARE({})".format(name))
        if name:
            share = getSharebyName(name)
            print("-- share name --> {} --".format(share.name))
            if share:
                share.show()
            else:
                print("share ({}) not found".format(name))
        else:
            for share in shares:
                print("-- share name --> {} --".format(share.name))
                share.show()
    else:
        print("no share listed in unity")


def showSNAP(name=None):
    # show snap detail (all snaps are displayed if no name arg is passed)
        # input -> snap name (if no input all snap will be printed)
        # output -> print only (no return)
    global shapshots
    snapshots = getSnaps()
    if debug > 0:
        print("calling showSNAP({})".format(name))
    if name:
        for snap in snapshots:
            if snap.name == name:
                snap.show()
        else:
            print("snap ({}) not found".format(name))
    else:
        print("\nList of all snapshots:\n")
        for snap in snapshots:
            print("  {}".format(snap.name))
            if debug > 0:
                snap.show()
                print("---")


def showFS(name=None):
    # show filesystem detail (all fs are displayed if no name arg is passed)
        # input -> filesystem name (if no input all fs will be printed)
        # output -> print only (no return)
    global fileSystems
    fileSystems = getFilesystems()
    if debug > 0:
        print("calling showFS({})".format(name))
    if name:
        fs = getFSbyName(name)
        if fs:
            fs.show()
        else:
            print("filesystem ({}) not found".format(name))
    else:
        for fs in fileSystems:
            fs.show()


def showNAS(name=None):
    global nasServers
    # show NAS server detail (all fs are displayed if no fsName arg is passed)
    # input -> nas server name (if no input all nas server will be printed)
    # output -> print only (no return)
    nasServers = getNASservers()
    if debug > 0:
        print("calling showNAS({})".format(name))
    if name:
        nas = getNASbyName(name)
        print("-- nas server name --> {} --".format(name))
        if nas:
            nas.show()
        else:
            print("NAS ({}) not found".format(name))
    else:
        for nas in nasServers:
            print("-- nas server name --> {} --".format(nas.name))
            nas.show()


def createNAS(name):
    # create nas server in unity given nas server name (uemcli execution)
    # input -> filesystem id (i.e. "res_1")
    # snap name will be set according to variable "snapshot"
    # output -> snapshot obj
    global cli
    global pool_id
    if name == "":
        print("empty nas name not allowed, exiting.")
        exit()
    cmd = "{} -u {} /net/nas/server create -name {} -sp spa -pool {}".format(
        cli, uemcli_user, name, pool_id)
    if debug > 0:
        print("calling createNAS({})".format(name))
        if debug > 1:
            print(cmd)
    try:
        output = subprocess.check_output(cmd, shell=True)
    except Exception as e:
        if debug > 0:
            print(e.output)
        print("could not create nas server with uemcli, exiting")
        exit()
        if (output.find("Operation completed successfully") >= 0) and (output.find("ID") >= 0):
            for nasline in output.splitline():
                if nasline.find("ID = "):
                    nas_id = nasline.split("=")[1].strip()
            # create nas server object of newly created snap
            # first get nas server entry from uemcli command filtering by nas_id
            # then create obj from output
            if nas_id.find("nas") >= 0:  # if find > 0 then string is found
                cmd = "{} /net/nas/server -id {} show -output csv".format(
                    cli, nas_id)
            try:
                output = subprocess.check_output(cmd, shell=True)
                nasline = output.splitlines()[1:]
                id, name, netbios, sp, poolname, tenant, interface, nfsEnabled, nfs3Enabled, nfs4Enabled, cifsEnabled, multiprotocol, unixDirectoryService, health = nasline.split(
                    ",")
                nas = Nasserver(id, name, netbios, sp, poolname, tenant, interface, nfsEnabled,
                                nfs3Enabled, nfs4Enabled, cifsEnabled, multiprotocol, unixDirectoryService, health)
                nasServers.append(nas)
                return nas
            except:
                print("could not create nas server object, exiting")
                exit()
                return None
            else:
                print("could not find nas server with id -> {} , exiting".format(nas_id))
                exit()
            return None

    return False


def showPROXYSHARE(nasname):
    # create a proxy nas server in unity by executing svc_nas
    # input -> string of proxy nas and nas server
    # true or false according to result of this command
    global nasServers
    global nasServer
    nasServers = getNASservers()
    if nasname and nasname != "":
        for nas in nasServers:
            if nas.name == nasname:
                nasServer = nas
                proxynas = nas.name + DRTEST_PROXYNAS_SUFFIX
                cmd = "sudo svc_nas {} -proxy_share -show".format(proxynas)
                if debug > 0:
                    print("calling showPROXYSHARE({}) ".format(nasname))
                os.system(cmd)
                exit()
        if not nasServer:
            print("Please specify a valid replicated nas server")
    else:
        print("Please specify a valid replicated nas server")


def showPROXY(nasname):
    # create a proxy nas server in unity by executing svc_nas
    # input -> string of proxy nas and nas server
    # true or false according to result of this command
    global nasServers
    global nasServer
    nasServers = getNASservers()
    if nasname and nasname != "":
        for nas in nasServers:
            if nas.name == nasname:
                nasServer = nas
                proxynas = nas.name + DRTEST_PROXYNAS_SUFFIX
                cmd = "sudo svc_nas {} -proxy -show".format(proxynas)
                if debug > 0:
                    print("calling showPROXY({}) ".format(nasname))
                os.system(cmd)
                exit()
        if not nasServer:
            print("Please specify a valid replicated nas server")
    else:
        print("Please specify a valid replicated nas server")


def createProxyNAS(proxynas, nas):
    # create a proxy nas server in unity by executing svc_nas
    # input -> string of proxy nas and nas server
    # true or false according to result of this command
    cmd = "sudo svc_nas {} -proxy -show".format(proxynas)
    output = ""
    if debug > 0:
        print("calling createProxyNAS({},{}) ".format(proxynas, nas))
        print("executing cmd:\n{}".format(cmd))
    try:
        # subprocess "svc_nas" must be run with shell=True
        output = subprocess.check_output(cmd, shell=True)
        if output.find("NAS server: ") >= 0 and output.find(nas.name) >= 0:
            print("found Proxy NAS ({}) already associated with nas server ({})".format(
                proxynas, nas.name))
        # cleanup = raw_input("do you want to clean existing shares ?")
        # svc_nas proxynas -proxy_share -show|grep "target=nas1 "
            return True
    except Exception as e:
        if (output.find("Error 4023:") >= 0) and (output.find("unknown host")):
            print("Proxy nas not yet created")
        if debug > 1:
            print(e.output)
        else:
            print("Cannot check proxy nas status...")

    print("Setting Proxy NAS ({}) association with nas server ({})".format(proxynas, nas))
    cmd = "sudo svc_nas {} -proxy -add {}".format(proxynas, nas.name)
    if debug > 0:
        print(cmd)
    try:
        # subprocess "svc_nas" must be run with shell=True
        output = subprocess.check_output(cmd, shell=True)
        print("done")
        return True
    except Exception as e:
        if debug > 0:
            print(e.message)
        print("cannot create proxy nas server ({}) of replicated nas server ({})".format(
            proxynas, nas.name))
        print("please check if it already exists:")
        cmd = "sudo svc_nas {} -proxy -show".format(proxynas)
    try:
        # subprocess "svc_nas" must be run with shell=True
        output = subprocess.check_output(cmd, shell=True)
    except Exception as e:
        if debug > 0:
            print(e.message)
        print("Error running svc_nas please check environment for other type of errors, exiting.")
        exit()
    return False


def deleteSNAP(snapID):
    # delete fs snapshot in unity given snapshot id (uemcli execution)
    # input -> snapshot id (i.e. "123456654321")
    # true or false according to operation succeed
    global cli
    cmd = "{} -u {} /prot/snap -id {} delete".format(cli, uemcli_user, snapID)
    if debug > 0:
        print("calling deleteSNAP({})".format(snapID))
        if debug > 1:
            print(cmd)
    try:
        output = subprocess.check_output(cmd, shell=True)
        return True
    except:
        return False


def createSNAP(fsID, snapname):
    # create fs snapshot in unity given fs id (uemcli execution)
    # input -> filesystem id (i.e. "res_1")
    # snap name will be set according to variable "snapshot"
    # output -> snapshot obj
    global snapshots
    global cli
    if snapname == "":
        print("empty snap name not allowed, exiting.")
        exit()
    cmd = "{} -u {} /prot/snap create -source {} -name {} -access share -keepFor {}".format(
        cli, uemcli_user, fsID, snapname, DRTEST_SNAP_RETENTION)
    if debug > 0:
        print("calling createSNAP({})".format(fsID))
        if debug > 1:
            print(cmd)
    try:
        output = subprocess.check_output(cmd, shell=True)
    except Exception as e:
        print("could not create snapshot:\n{}".format(e.output))
        if debug > 0:
            print(e)
        exit()
    # check if command return a successful message
    snap_id = (output.split("\n")[0]).split(" = ")[1]
    cmd = "{} /prot/snap -id {} show -output csv".format(cli, snap_id)
    if debug > 0:
        print("snap name --> ({}) snap_id --> ({})".format(snapname, snap_id))
    try:
        # create snapshot object of newly created snap
        # first get snap entry from uemcli command filtering by snap_id
        # then create obj from output
        output = subprocess.check_output(cmd, shell=True)
        snapline = output.splitlines()[1:]
        if debug > 1:
            print(snapline)
        id, name, state, attached, source, sourceType, members, attachDetails = snapline[0].split(
            ",")
        s = Snapshot(id, name, state, attached, source,
                     sourceType, members, attachDetails)
        snapshots.append(s)
        return s
    except Exception as e:
        print("could not create snapshot object, exiting")
        print(e.message)
        exit()
        return None
    else:
        print("could not find snapshot with id -> {} , exiting".format(snap_id))
        exit()
    return None


def createFsSnap(fsname, snapname):
    # create snapshot of a filesystem
    # input -> filesystem name and snapshot name
    # output -> print only
    global fileSystems
    global snapshots
    global debug
    if debug > 0:
        print("Calling createFsSnap({},{})".format(fsname, snapname))
    fileSystems = getFilesystems()
    if snapname == "":
        snapshots = getSnaps()
        x = 1
        not_found = True
        while not_found:
            if debug > 0:
                print("check if snapshot name is already used")
            snapname = fsname + "_snap" + str(x)
            snap = findSNAP(snapname)
            if snap:
                if debug > 0:
                    print("snapshot name ({}) already used".format(snapname))
                x += 1
            else:
                not_found = False  # snapshot found
    fs = getFSbyName(fsname)
    if fs:

        print("Creating snapshot name ({}) of filesystem ({})".format(snapname, fsname))
        snap = createSNAP(fs.id, snapname)
        if snap:
            print("{}\nSnap created successfully".format(snap.show()))
        else:
            print("error snap -> ({})".format(snap))
    else:
        print("Could not find filesystem please check your command")
    exit()


def sendSUDOCMD(cmd):
    try:
        output = subprocess.check_output(cmd, shell=True)
        return output
    except Exception as e:
        print(e.message)
        return None


def proxyshareCOPY(list_of_shares, snap, proxynas, nasname):
    # copy list of shares from nas server to proxy name
    # input -> list of share obj, snap object and string proxynas name
    # output -> True or False according to the results
    if debug > 0:
        print("calling proxyshareCOPY({},{},{}) ".format(
            list_of_shares, snap.name, proxynas, nasname))
    global shares
    global snapshot
    shares = getShares()
    fileSystem_ids = []
    fileSystem_ids = getFSidsByNasID(nas.id)
    cmd = "sudo svc_nas {} -proxy_share -show".format(proxynas)
    try:
        # subprocess "svc_nas" must be run with shell=True
        print("Check if Proxy Shares are already available in Proxy NAS server ({})".format(
            proxynas))
        output = subprocess.check_output(cmd, shell=True)
    except Exception as e:
        print("Cannot check proxy nas status, exiting")
        exit()
    for share in list_of_shares:
        proxy_share_path = "/" + snap.name + share.path
        proxy_share_name = share.name
        if share.filesystem == snap.source:  # compare filesystem id of share and snap
            if output.find(proxy_share_name) >= 0:
                if debug > 0:
                    print("Proxy share ({}) already present in Proxy NAS server ({})".format(
                        share.name, proxynas))
                removecmd = "sudo svc_nas {} -proxy_share -remove -share {}".format(
                    proxynas, proxy_share_name)
                cmdoutput = sendSUDOCMD(removecmd)
                if (cmdoutput.find(" : commands processed: 1") >= 0) and (cmdoutput.find("command(s) succeeded") >= 0):
                    if debug > 0:
                        print("Deleted Proxy share ({}) already present in Proxy NAS server ({})".format(
                            share.name, proxynas))
            addsharecmd = "sudo svc_nas {} -proxy_share -add {} -share {} -path {}".format(
                proxynas, nasname, proxy_share_name, proxy_share_path)
            cmdoutput = sendSUDOCMD(addsharecmd)
            if (cmdoutput.find(" : commands processed: 1") >= 0) and (cmdoutput.find("command(s) succeeded") >= 0):
                if debug > 0:
                    print("Added Proxy share ({}) in Proxy NAS server ({})".format(
                        share.name, proxynas))
            else:
                # error return false
                return False
    return True


def proxyshareDUP(proxynas, nas):
    # duplicate proxy share copying from nas server replication
    # input -> nas and proxy nas objects
    # output -> True or False according to the results
    if debug > 0:
        print("calling proxyshareDUP({},{}) ".format(proxynas, nas))
    global shares
    global snapshot
    shares = getShares()
    fileSystem_ids = []
    fileSystem_ids = getFSidsByNasID(nas.id)
    cmd = "sudo svc_nas {} -proxy_share -show".format(proxynas)
    try:
            # subprocess "svc_nas" must be run with shell=True
        print("Check if Proxy Shares are already available in Proxy NAS server ({})".format(
            proxynas))
        output = subprocess.check_output(cmd, shell=True)
    except Exception as e:
        print("Cannot check proxy nas status, exiting")
        exit()
    for share in shares:
        if share.filesystem in fileSystem_ids:
            if output.find("/" + snapshot + share.path) >= 0:
                print("Proxy share ({}) already available in Proxy NAS server ({})".format(
                    share.name, proxynas))
            else:
                path = "/" + snapshot + share.path
                cmd = "sudo svc_nas {} -proxy_share -add {} -share {} -path {}".format(
                    proxynas, nas.name, share.name, path)
                if debug > 0:
                    print(cmd)
                try:
                    print("Copy Proxy share ({}) to Proxy NAS server ({}).".format(
                        share.name, proxynas))
                    # subprocess "svc_nas" must be run with shell=True
                    output = subprocess.check_output(cmd, shell=True)
                except Exception as e:
                    if output.find("") >= 0:  # check if output contains "already exists"
                        print("Proxy share ({}) with path ({}) already exists in server ({})".format(
                            share.name, path, proxynas))
                    else:
                        print("Cannot copy proxy share...")
                        exit()
    return True


def findNAS(name):
    # find return (if found) a nas server given a name in input
    # input -> nas server name (i.e. "nas1")
    # output -> nas server object or None
    if debug > 0:
        print("calling findNAS({})".format(name))
    for nas in nasServers:
        if nas.name == name:
            return nas
    return None


def getSnapByName(snapname):
    # find return (if found) a snapshot object given a snap name in input
    # input -> snapshot name (i.e. "snap1")
    # output -> snapshot object or None
    global snapshots
    if debug > 0:
        print("calling getSnapByName({})".format(snapname))
    for snap in snapshots:
        if snap.name == snapname:
            return snap
    return None


def getSnapByID(snapID):
    # find return (if found) a snapshot object given a snap id in input
    # input -> snapshot id (i.e. "snap_id")
    # output -> snapshot object or None
    global snapshots
    if debug > 0:
        print("calling getSnapByID({})".format(snapID))
    for snap in snapshots:
        if snap.id == snapID:
            return snap
    return None


def findSNAP(name):
    # find return (if found) a snapshot object given a name in input
    # input -> snapshot name (i.e. "snap1")
    # output -> snapshot object or None
    if debug > 0:
        print("calling findSNAP({})".format(name))
    for snap in snapshots:
        if snap.name == name:
            return snap
    return None


def snap_filesystem(filesystem):
    pass


def getNASfsList(nasobj):
    # return a list of filesystem objects that belong to a nas server
    # input -> nas server obj
    # output -> nas obj list
    filesystem_list = []
    for fs in fileSystems:
        if fs.server == nas.id:
            filesystem_list.append(fs)
    return filesystem_list


def createDrProxy(nas):
    # create or reuse existing proxy NAS of a given nas server
    # input -> nas object
    # output -> true or false according to result
    proxyNAS_name = nas.name + DRTEST_PROXYNAS_SUFFIX
    proxyNAS = findNAS(proxyNAS_name)
    if proxyNAS:
        print("Proxy NAS server ({}) already present".format(proxyNAS_name))
        print("setting it as proxy nas of NAS server ({})".format(nas.name))
    else:
        print("Proxy NAS server ({}) not present, creating it...".format(proxyNAS_name))
        proxyNAS = createNAS(proxyNAS_name)
        print("setting it as proxy nas of NAS server ({})".format(nas.name))
    return createProxyNAS(proxyNAS_name, nas)


def createDrSnap(fs):
    # create or reuse existing snapshot of a given filesystem
    # input -> fs object
    # output -> snap object
    global snapshot
    snapshot = fs.name + DRTEST_SNAP_SUFFIX
    snap = findSNAP(snapshot)
    if snap:  # snap is found
        print("\nSnap for DR testing is already present ({})".format(snap.name))
        if debug > 0:
            snap.show()
            print("-----")
        reuse = ""
        try:
            reuse = raw_input(
                "snap ({}) already exists, do you wish to use this for DR testing ? [y/n]: ".format(snapshot))
        except KeyboardInterrupt:
            print("\nUser interruption, exiting")
            exit()
        if (reuse == "y") or (reuse == "yes") or (reuse == "Y"):
            pass
        elif (reuse == "n") or (reuse == "no") or (reuse == "N"):
            delete = ""
            try:
                delete = raw_input(
                    "do you wish to delete it and recreate it with the same name ? [y/n]: ")
            except KeyboardInterrupt:
                print("\nUser interruption, exiting")
                exit()
            if (delete == "y") or (delete == "yes") or (delete == "Y"):
                print("deleting snap ({})".format(snap.name))
                if deleteSNAP(snap.id):
                    print("creating snap ({})".format(snap.name))
                    snap = createSNAP(fs.id, snapshot)
                else:
                    print("Failed deleting snap ({}) of filesystem ({}) , exiting.".format(
                        snap.id, fs.name))
                    exit()
            elif (delete == "n") or (delete == "no") or (delete == "N"):
                snapshot = raw_input(
                    "Please enter fs ({}) snapshot name that will be used: ".format(fs.name))
                print("creating snap ({})".format(snapshot))
                snap = createSNAP(fs.id, snapshot)
        else:
            print("not sure what you want to do with snapshot, exiting.")
            exit()
    else:
        # end comma will make print stay on the same line
        print "creating snap ({})".format(snapshot),
        snap = createSNAP(fs.id, snapshot)
        print(snap)
        if debug > 0:
            print(snap.show())
    return snap


if __name__ == '__main__':
    fs = None
    nas = None
    snap = None
    pool = None
    is_proxy_nas_server_present = False
    if cmdParser():
        print("\nSet up DR testing environment for NAS server ({})".format(nasServer))
        print("Getting system info...")
        fileSystems = getFilesystems()
        nasServers = getNASservers()
        snapshots = getSnapshots()
        shares = getShares()
        pool = getPools()
        fs = getFSbyName(fileSystem)
        nas = getNASbyName(nasServer)
        if len(fileSystems) == 0:  # if found fs in not Null
            print("No filesystems found in this system")
            exit()
        if len(nasServers) == 0:  # if found fs in not Null
            print("No NAS servers found in this system")
            exit()
        if not fs and (fileSystem):
            print("fs name ({}) not found in filesystem list".format(fileSystem))
            print(
                "Please check in this File System list (total: {})\n-------".format(len(fileSystems)))
            printFSlist()
            exit()
            # need to be completed
        if nas:  # if found nas in not Null
            pool_id = nas.poolname
            fs_snap_list = getNASfsList(nas)
            if debug > 0:
                for fs in fs_snap_list:
                    print(fs.name)
            if len(fs_snap_list) > 0:
                if debug > 0:
                    print(
                        "NAS server name ({}) found in filesystem list".format(nasServer))
                if (fileSystem != "") and (nas.id != fs.server):
                    print("filesystem ({}) and ({}) do not match".format(
                        filesystem, nasServer))
                    nas = getNASbyID(fs.server)
                    print("according to Unity filesystem ({}) matches with NAS Server ({})".format(
                        fs.name, nas.name))
                    exit()
        else:
            print("NAS server name ({}) not found in filesystem list".format(nasServer))
            print("Please check in this NAS server list\n-------")
            printNASlist()
            exit()
        proxyNAS_name = nas.name + DRTEST_PROXYNAS_SUFFIX
        # create or update proxy NAS
        createDrProxy(nas)
        # get all fs belonging to NAS server
        nasfs_list = getNASfsList(nas)
        # for every fs create the snapshot and proxy shares
        for fs in nasfs_list:
            sharelist = []
            snap = createDrSnap(fs)
            if not snap:
                print("Create DR snap failed for FS ({})".format(fs.name))
                exit()
            # create share
            # get shares exported from this filesystem
            for share in shares:
                if share.filesystem == fs.id:
                    sharelist.append(share)
            # copyShare(sharelist, snap.name, proxyNAS_name)
            if len(sharelist) > 0:
                ok_result = proxyshareCOPY(
                    sharelist, snap, proxyNAS_name, nas.name)
                if ok_result:
                    print("\nProxy shares copied for file system ({})".format(fs.name))
                else:
                    print(
                        "\nProxy shares copy failed for file system ({})".format(fs.name))
                    exit()
        print("DR test environment ready for proxy NAS ({})".format(proxyNAS_name))
    else:
        usage()
