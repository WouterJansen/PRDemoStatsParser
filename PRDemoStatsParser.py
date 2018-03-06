import sys
import struct
import zlib
import cStringIO
import json
import os, os.path
import errno
from collections import namedtuple
from fnmatch import fnmatch
import datetime
import time
from bs4 import BeautifulSoup
import requests
import urllib

###############################
#           HELPERS           #
###############################

# Helper functions to turn json files into namedtuple
def _json_object_hook(d): return namedtuple('X', d.keys())(*d.values())
def json2obj(data): return json.loads(data, object_hook=_json_object_hook)


# Helper functions to safely create new folders if it doesn't exist already
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise
def safe_open_w(path):
    mkdir_p(os.path.dirname(path))
    return open(path, 'w')


# Helper function to return a null terminated string from pos in buffer
def getString(stream):
    tmp = ''
    while True:
        char = stream.read(1)
        if char == '\0':
            return tmp
        tmp += char


# Helper function to add to struct.unpack null terminated strings
# Unpacks with null terminated strings when using "s".
# Unpacks "vehicle" structs when using "v".
# Returns a list of [value1,value2,value3...]
def unpack(stream, fmt):
    values = []

    for i in range(0, len(fmt)):
        if fmt[i] == 'v':
            vehid = unpack(stream, "h")
            if vehid >= 0:
                (vehname, vehseat) = unpack(stream, "sb")
                values.append((vehid, vehname, vehseat))
            else:
                values.append((vehid))

        elif fmt[i] == 's':
            string = getString(stream)
            values.append(string)
        else:
            size = struct.calcsize(fmt[i])
            try:
                values.append(struct.unpack("<" + fmt[i], stream.read(size))[0])
            except:
                return -1;
    if len(values) == 1:
        return values[0]
    return values

# Helper function to through a folder and list all files
def walkdir(folder):
    for dirpath, dirs, files in os.walk(folder):
        for filename in files:
            yield os.path.abspath(os.path.join(dirpath, filename))

# Helper function to show progress bar
def update_progress(progress,message):
    barLength = 20
    status = message
    if isinstance(progress, int):
        progress = float(progress)
    if not isinstance(progress, float):
        progress = 0
        status = "error: progress var must be float\r\n"
    if progress < 0:
        progress = 0
        status = "Halt...\r\n"
    if progress >= 1:
        progress = 1
        status = "\r\n"
    block = int(round(barLength*progress))
    text = "\r[{0}] {1}% {2}".format( "#"*block + "-"*(barLength-block), round(progress*100,2), status)
    sys.stdout.write(text)
    sys.stdout.flush()


###############################
#           CLASSES           #
###############################

class Flag(object):

    def __init__(self, cpid, x, y, z, radius):
        self.cpid = cpid
        self.x = x
        self.y = y
        self.z = z
        self.radius = radius


class ParsedDemo(object):

    def __init__(self,version=0, date=0, map=0, gameMode=0, layer=0, duration=0, playerCount=0, ticketsTeam1=0, ticketsTeam2=0,
                 flags=[]):
        self.version = version
        self.map = map
        self.date = date
        self.gameMode = gameMode
        self.layer = layer
        self.duration = duration
        self.playerCount = playerCount
        self.ticketsTeam1 = ticketsTeam1
        self.ticketsTeam2 = ticketsTeam2
        self.flags = flags

    def setData(self, version, date, map, gameMode, layer, duration, playerCount, ticketsTeam1, ticketsTeam2, flags):
        self.version = version
        self.date = date
        self.map = map
        self.gameMode = gameMode
        self.layer = layer
        self.duration = duration
        self.playerCount = playerCount
        self.ticketsTeam1 = ticketsTeam1
        self.ticketsTeam2 = ticketsTeam2
        self.flags = flags

    # TODO Implement SGID method
    # Create ID of flag route based on CPID list (placeholder until SGID is available to calculate route ID)
    def getFlagId(self):
        flagCPIDs = []
        for flag in self.flags:
            flagCPIDs.append(flag.cpid)
        flagCPIDs.sort()
        return ("Route " + ", ".join(str(x) for x in flagCPIDs)).strip()


class ServerList(object):

    def __init__(self):
        self.date = str(datetime.datetime.now())
        self.servers = []

    # Write object to JSON string
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)


class Server(object):

    def __init__(self,name,links,demos):
        self.name = name;
        self.links = links
        self.demos = demos;


class MapList(object):

    def __init__(self):
        self.maps = []
        self.date = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

    # Write object to JSON string
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)


class Map(object):

    def __init__(self, name):
        self.name = name
        self.gameModes = []
        self.timesPlayed = 0
        self.averageDuration = 0
        self.averageTicketsTeam1 = 0
        self.averageTicketsTeam2 = 0
        self.winsTeam1 = 0
        self.winsTeam2 = 0
        self.draws = 0
        self.versions =  []

    # Write object to JSON string
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)


class GameMode(object):

    def __init__(self, name):
        self.name = name
        self.layers = []
        self.timesPlayed = 0
        self.averageDuration = 0
        self.averageTicketsTeam1 = 0
        self.averageTicketsTeam2 = 0
        self.winsTeam1 = 0
        self.winsTeam2 = 0
        self.draws = 0


class Layer(object):

    def __init__(self, name):
        self.name = name
        self.routes = []
        self.timesPlayed = 0
        self.averageDuration = 0
        self.averageTicketsTeam1 = 0
        self.averageTicketsTeam2 = 0
        self.winsTeam1 = 0
        self.winsTeam2 = 0
        self.draws = 0


class Route(object):

    def __init__(self, id):
        self.id = id
        self.roundsPlayed = []
        self.timesPlayed = 0
        self.averageDuration = 0
        self.averageTicketsTeam1 = 0
        self.averageTicketsTeam2 = 0
        self.winsTeam1 = 0
        self.winsTeam2 = 0
        self.draws = 0


# Parse .PRdemo file
class demoParser:
    def __init__(self, filename):
        compressedFile = open(filename, 'rb')
        compressedBuffer = compressedFile.read()
        compressedFile.close()
        # Try to decompress or assume its not compressed if it fails
        try:
            buffer = zlib.decompress(compressedBuffer)
        except:
            buffer = compressedBuffer
        ####
        self.stream = cStringIO.StringIO(buffer)
        self.length = len(buffer)

        self.players = 0
        self.timePlayed = 0
        self.flags = []
        self.parsedDemo = ParsedDemo()
        # parse the first few until serverDetails one to get map info
        timeoutindex = 0
        while self.runMessage() != 0x00:
            if timeoutindex == 10000:
                break
            timeoutindex += 1
            pass
        self.runToEnd()

        # create ParsedDemo object and set it to complete if it was able to get alld data
        try:
            self.parsedDemo.setData(self.version, self.date, self.mapName, self.mapGamemode, self.mapLayer, self.timePlayed / 60,
                                    self.players,
                                    self.ticket1, self.ticket2, self.flags)
            self.parsedDemo.completed = True
        except:
            pass

    def getParsedDemo(self):
        return self.parsedDemo

    def runMessage(self):
        # Check if end of file
        tmp = self.stream.read(2)
        if len(tmp) != 2:
            return 0x99

        # Get 2 bytes of message length
        messageLength = struct.unpack("H", tmp)[0]

        startPos = self.stream.tell()
        try:
            messageType = struct.unpack("B", self.stream.read(1))[0]
        except:
            return 0x99

        if messageType == 0x00:  # server details
            values = unpack(self.stream, "IfssBHHssBssIHH")
            if values == -1: return 0x99
            version = values[3].split(']')[0].split(' ')
            self.version = version[1]
            self.mapName = values[7]
            gamemode = values[8]
            if gamemode == "gpm_cq":
                self.mapGamemode = "Advance & Secure"
            elif gamemode == "gpm_insurgency":
                self.mapGamemode = "Insurgency"
            elif gamemode == "gpm_vehicles":
                self.mapGamemode = "Vehicle Warfare"
            elif gamemode == "gpm_cnc":
                self.mapGamemode = "Command & Control"
            elif gamemode == "gpm_skirmish":
                self.mapGamemode = "Skirmish"
            elif gamemode == "gpm_coop":
                self.mapGamemode = "Co-Operative"
            else:
                self.mapGamemode = values[8]
            self.mapLayer = "Layer " + str(values[9])
            self.date = values[12]

        elif messageType == 0x52:  # tickets team 1
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "H")
                if values == -1: return 0x99
                if values < 9000:
                    self.ticket1 = values

        elif messageType == 0x53:  # tickets team 2
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "H")
                if values == -1: return 0x99
                if values < 9000:
                    self.ticket2 = values

        elif messageType == 0xf1:  # tick
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "B")
                if values == -1: return 0x99
                self.timePlayed = self.timePlayed + values * 0.04

        elif messageType == 0x11:  # add player
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "Bsss")
                if values == -1: return 0x99
                self.players = self.players + 1

        elif messageType == 0x12:  # remove player
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "B")
                if values == -1: return 0x99
                self.players = self.players - 1

        elif messageType == 0x41:  # flaglist
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "HBHHHH")
                if values == -1: return 0x99
                self.flags.append(Flag(values[0], values[2], values[3], values[4], values[5]))

        else:
            self.stream.read(messageLength - 1)
        return messageType

    # Returns when tick or round end recieved.
    # Returns false when roundend message recieved
    def runTick(self):
        while True:
            messageType = self.runMessage()
            if messageType == 0xf1:
                return True
            if messageType == 0xf0:
                return False
            if messageType == 0x99:
                return False

    def runToEnd(self):
        while self.runTick():
            pass

class StatsParser:
    versions = {}
    def __init__(self):
        self.downloadDemos()
        self.importStats()
        self.dataAggragation()
        self.statsCalc()
        self.exportStats()
        self.createMapList()

    # Calculate statistics such as times played and average tickets based on data
    def statsCalc(self):
        print "Calculating Statistics..."
        for versionname,version in self.versions.iteritems():
            for mapname, map in version.iteritems():
                mapTotalTickets1 = 0
                mapTotalTickets2 = 0
                mapTotalDuration = 0
                for gameModeIndex, gameMode in enumerate(map.gameModes, start=0):
                    gamemodeTotalTickets1 = 0
                    gamemodeTotalTickets2 = 0
                    gamemodeTotalDuration = 0
                    for layerIndex, layer in enumerate(gameMode.layers, start=0):
                        layerTotalTickets1 = 0
                        layerTotalTickets2 = 0
                        layerTotalDuration = 0
                        for routeIndex, route in enumerate(layer.routes, start=0):
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].routes[
                                routeIndex].timesPlayed = len(route.roundsPlayed)
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].timesPlayed += len(
                                route.roundsPlayed)
                            self.versions[versionname][mapname].gameModes[gameModeIndex].timesPlayed += len(route.roundsPlayed)
                            self.versions[versionname][mapname].timesPlayed += len(route.roundsPlayed)
                            routeTotalTickets1 = 0
                            routeTotalTickets2 = 0
                            routeTotalDuration = 0
                            winsTeam1 = 0
                            winsTeam2 = 0
                            draws = 0
                            for parsedDemo in route.roundsPlayed:
                                if parsedDemo.ticketsTeam1 > parsedDemo.ticketsTeam2:
                                    winsTeam1 += 1
                                elif parsedDemo.ticketsTeam2 > parsedDemo.ticketsTeam1:
                                    winsTeam2 += 1
                                else:
                                    draws += 1
                                routeTotalTickets1 += parsedDemo.ticketsTeam1
                                routeTotalTickets2 += parsedDemo.ticketsTeam2
                                routeTotalDuration += parsedDemo.duration
                                layerTotalTickets1 += parsedDemo.ticketsTeam1
                                layerTotalTickets2 += parsedDemo.ticketsTeam2
                                layerTotalDuration += parsedDemo.duration
                                gamemodeTotalTickets1 += parsedDemo.ticketsTeam1
                                gamemodeTotalTickets2 += parsedDemo.ticketsTeam2
                                gamemodeTotalDuration += parsedDemo.duration
                                mapTotalTickets1 += parsedDemo.ticketsTeam1
                                mapTotalTickets2 += parsedDemo.ticketsTeam2
                                mapTotalDuration += parsedDemo.duration

                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].routes[
                                routeIndex].averageTicketsTeam1 = routeTotalTickets1 / len(route.roundsPlayed)
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].routes[
                                routeIndex].averageTicketsTeam2 = routeTotalTickets2 / len(route.roundsPlayed)
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].routes[
                                routeIndex].averageDuration = routeTotalDuration / len(route.roundsPlayed)
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].routes[
                                routeIndex].winsTeam1 = winsTeam1
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].routes[
                                routeIndex].winsTeam2 = winsTeam2
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].routes[routeIndex].draws += draws
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].winsTeam1 += winsTeam1
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].winsTeam2 += winsTeam2
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[layerIndex].draws += draws
                            self.versions[versionname][mapname].gameModes[gameModeIndex].winsTeam1 += winsTeam1
                            self.versions[versionname][mapname].gameModes[gameModeIndex].winsTeam2 += winsTeam2
                            self.versions[versionname][mapname].gameModes[gameModeIndex].draws += draws
                            self.versions[versionname][mapname].winsTeam1 += winsTeam1
                            self.versions[versionname][mapname].winsTeam2 += winsTeam2
                            self.versions[versionname][mapname].draws += draws
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[
                            layerIndex].averageTicketsTeam1 = layerTotalTickets1 / \
                                                              self.versions[versionname][mapname].gameModes[gameModeIndex].layers[
                                                                  layerIndex].timesPlayed
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[
                            layerIndex].averageTicketsTeam2 = layerTotalTickets2 / \
                                                              self.versions[versionname][mapname].gameModes[gameModeIndex].layers[
                                                                  layerIndex].timesPlayed
                            self.versions[versionname][mapname].gameModes[gameModeIndex].layers[
                            layerIndex].averageDuration = layerTotalDuration / \
                                                          self.versions[versionname][mapname].gameModes[gameModeIndex].layers[
                                                              layerIndex].timesPlayed
                            self.versions[versionname][mapname].gameModes[gameModeIndex].averageTicketsTeam1 = gamemodeTotalTickets1 / \
                                                                                                                      self.versions[
                                                                                                                          versionname][mapname].gameModes[
                                                                                          gameModeIndex].timesPlayed
                            self.versions[versionname][mapname].gameModes[gameModeIndex].averageTicketsTeam2 = gamemodeTotalTickets2 / \
                                                                                                                      self.versions[
                                                                                                                          versionname][mapname].gameModes[
                                                                                          gameModeIndex].timesPlayed
                            self.versions[versionname][mapname].gameModes[gameModeIndex].averageDuration = gamemodeTotalDuration / \
                                                                                                                  self.versions[
                                                                                                                      versionname][mapname].gameModes[
                                                                                      gameModeIndex].timesPlayed
                            self.versions[versionname][mapname].averageTicketsTeam1 = mapTotalTickets1 / self.versions[versionname][mapname].timesPlayed
                            self.versions[versionname][mapname].averageTicketsTeam2 = mapTotalTickets2 / self.versions[versionname][mapname].timesPlayed
                            self.versions[versionname][mapname].averageDuration = mapTotalDuration / self.versions[versionname][mapname].timesPlayed
        print "Statistics Calculated."

    # Map the parsedDemo to the correct structure in the statistics based on Map,GameMode,Layer,Route
    def demoToData(self, parsedDemo):
        if parsedDemo.map != 0 and ((parsedDemo.gameMode !="gpm_skirmish" and parsedDemo.playerCount > 80) or (parsedDemo.gameMode =="gpm_skirmish" and parsedDemo.playerCount > 20)):
            if parsedDemo.version in self.versions:
                if parsedDemo.map in self.versions[parsedDemo.version]:
                    gameModeFound = False
                    for gameModeIndex, gameMode in enumerate(self.versions[parsedDemo.version][parsedDemo.map].gameModes, start=0):
                        if gameMode.name == parsedDemo.gameMode:
                            layerFound = False
                            for layerIndex, layer in enumerate(self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers,
                                                               start=0):
                                if layer.name == parsedDemo.layer:
                                    routeFound = False
                                    for routeIndex, route in enumerate(
                                            self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers[
                                                layerIndex].routes, start=0):
                                        if route.id == parsedDemo.getFlagId():
                                            self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers[
                                                layerIndex].routes[routeIndex].roundsPlayed.append(parsedDemo)
                                            routeFound = True
                                    if not routeFound:
                                        self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers[
                                            layerIndex].routes.append(Route(parsedDemo.getFlagId()))
                                        self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers[
                                            layerIndex].routes[-1].roundsPlayed.append(parsedDemo)
                                layerFound = True
                            if not layerFound:
                                self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers.append(Layer(parsedDemo.layer))
                                self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers[-1].routes.append(
                                    Route(parsedDemo.getFlagId()))
                                self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers[-1].routes[0].roundsPlayed.append(
                                    parsedDemo)
                            gameModeFound = True
                    if not gameModeFound:
                        self.versions[parsedDemo.version][parsedDemo.map].gameModes.append(GameMode(parsedDemo.gameMode))
                        self.versions[parsedDemo.version][parsedDemo.map].gameModes[-1].layers.append(Layer(parsedDemo.layer))
                        self.versions[parsedDemo.version][parsedDemo.map].gameModes[-1].layers[0].routes.append(Route(parsedDemo.getFlagId()))
                        self.versions[parsedDemo.version][parsedDemo.map].gameModes[-1].layers[0].routes[0].roundsPlayed.append(parsedDemo)
                else:
                    self.versions[parsedDemo.version][parsedDemo.map] = Map(parsedDemo.map)
                    self.versions[parsedDemo.version][parsedDemo.map].gameModes.append(GameMode(parsedDemo.gameMode))
                    self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers.append(Layer(parsedDemo.layer))
                    self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers[0].routes.append(Route(parsedDemo.getFlagId()))
                    self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers[0].routes[0].roundsPlayed.append(parsedDemo)
            else:
                self.versions[parsedDemo.version] = {}
                self.versions[parsedDemo.version][parsedDemo.map] = Map(parsedDemo.map)
                self.versions[parsedDemo.version][parsedDemo.map].gameModes.append(GameMode(parsedDemo.gameMode))
                self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers.append(
                    Layer(parsedDemo.layer))
                self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers[0].routes.append(
                    Route(parsedDemo.getFlagId()))
                self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers[0].routes[
                    0].roundsPlayed.append(parsedDemo)

    # Parse all PRdemo files in the demos folder. It also removes the files after parsing to avoid duplicate entries
    def dataAggragation(self):
        print "Parsing new PRDemos..."
        filecounter = 0
        for filepath in walkdir("./demos"):
            filecounter += 1
        if filecounter != 0:
            for index, filepath in enumerate(walkdir("./demos"), start=0):
                head, tail = os.path.split(filepath)
                parsedDemo = demoParser(filepath).getParsedDemo()
                self.demoToData(parsedDemo)
                update_progress(float(index)/filecounter,"(" + str(index) + "/" + str(filecounter) + ") " + tail)
            update_progress(1,"")
            sys.stdout.flush()

            filelist = [f for f in os.listdir("./demos") if f.endswith(".PRdemo")]
            for f in filelist:
                os.remove(os.path.join("./demos", f))
            print "Parsing of new PRDemos(" + str(filecounter) +") complete."
        else:
            print "No PRDemos found."

    # Export the statistics to the /maps/mapname/data.json files
    def exportStats(self):
        print "Exporting statistics..."
        for versionname,version in self.versions.iteritems():
            for mapname, map in version.iteritems():
                with safe_open_w("./maps/" + versionname + "/" + mapname + "/data.json") as f:
                    f.write(map.toJSON())
        print "Export of statistics complete."

    # Create maplist.json with basic map statistics for map list overview
    def createMapList(self):
        print "Creating maplist..."
        mapList = MapList()
        foundMapNames = False
        try:
            with open("./maps.json", 'r') as f:
                mapNamesData = f.read()
                mapNames = json2obj(mapNamesData)
                foundMapNames = True
        except:
            pass
        for versionname,version in self.versions.iteritems():
            for mapname, mapObject in version.iteritems():
                mapfound = False
                for index, map in enumerate(mapList.maps, start=0):
                    if map.name == mapname:
                        mapfound = True
                        mapList.maps[index].versions.append(versionname)
                        mapList.maps[index].timesPlayed += mapObject.timesPlayed
                        mapList.maps[index].winsTeam1 += mapObject.winsTeam1
                        mapList.maps[index].winsTeam2 += mapObject.winsTeam2
                        mapList.maps[index].draws += mapObject.draws
                        mapList.maps[index].averageDuration = (mapList.maps[index].averageDuration + mapObject.averageDuration) / 2
                        mapList.maps[index].averageTicketsTeam1 = (mapList.maps[
                                                                   index].averageTicketsTeam1 + mapObject.averageTicketsTeam1) / 2
                        mapList.maps[index].averageTicketsTeam2 = (mapList.maps[
                                                                   index].averageTicketsTeam2 + mapObject.averageTicketsTeam2) / 2
                if mapfound == False:
                    if foundMapNames:
                        if hasattr(mapNames, mapname):
                            mapObject.displayName = getattr(mapNames,mapname)
                        else:
                            mapObject.displayName = mapname
                    else:
                        mapObject.displayName = mapname
                    mapObject.versions.append(versionname)
                    del mapObject.gameModes
                    mapList.maps.append(mapObject)
        for versionname, version in self.versions.iteritems():
            for mapname, mapObject in version.iteritems():
                mapObject.versions.sort()
        with safe_open_w("./maps/maplist.json") as f:
            f.write(mapList.toJSON())
        print "Created maplist."

    # Import existing data.json files of each map and gets the parsedDemos to be able to re-calculate the statistics
    def importStats(self):
        print "Importing existing statistics..."
        filecounter = -1
        for filepath in walkdir("./maps"):
            filecounter += 1
        if filecounter > 1:
            for index, filepath in enumerate(walkdir("./maps"), start=0):
                if fnmatch(filepath, "*.json") and fnmatch(filepath, "*maplist.json") is False:
                    head, tail = os.path.split(filepath)
                    with open(filepath, 'r') as f:
                        mapData = f.read()
                        mapObject = json2obj(mapData)
                        for gamemode in mapObject.gameModes:
                            for layer in gamemode.layers:
                                for route in layer.routes:
                                    for parsedDemo in route.roundsPlayed:
                                        flags = []
                                        for flag in parsedDemo.flags:
                                            flags.append(Flag(flag.cpid, flag.x, flag.y, flag.z, flag.radius))
                                        newDemo = ParsedDemo(parsedDemo.version, parsedDemo.date, str(parsedDemo.map),
                                                             str(parsedDemo.gameMode), str(parsedDemo.layer),
                                                             parsedDemo.duration, parsedDemo.playerCount,
                                                             parsedDemo.ticketsTeam1, parsedDemo.ticketsTeam2, flags)
                                        newDemo.completed = True
                                        self.demoToData(newDemo)
                    update_progress(float(index)/filecounter, "(" + str(index) + "/" + str(filecounter) + ") " + os.path.split(os.path.split(head)[0])[1] + "/" + os.path.basename(os.path.normpath(head)))
            print "Import of existing statistics(" + str(filecounter) + ") complete."
        else:
            print "No existing statistics found."

    def downloadDemos(self):
        newServerList = ServerList()
        with open('./servers.json', 'r') as f:
            serverData = f.read()
            serverList = json2obj(serverData)
            toDownload = []
            toDownloadServerNames = []
            serverListNames = []
            for serverIndex, server in enumerate(serverList.servers, start=0):
                links = []
                demos = server.demos
                for linkIndex, link in enumerate(server.links, start=0):
                    links.append(link)
                    soup = BeautifulSoup(requests.get(link).text, 'html.parser')
                    for demoUrl in [link + node.get('href') for node in soup.find_all('a') if
                                    node.get('href').endswith('PRdemo')]:
                        if os.path.basename(demoUrl) not in server.demos:
                            if server.name not in serverListNames:
                                serverListNames.append(server.name)
                            toDownload.append(demoUrl)
                            toDownloadServerNames.append(server.name)
                            demos.append(os.path.basename(demoUrl))
                newServerList.servers.append(Server(server.name, links, demos))
            print "Downloading PRDemos from servers(" + ','.join(serverListNames) + ")..."
            for demoIndex, demoUrl in enumerate(toDownload, start=0):
                update_progress(float(demoIndex) / len(toDownload),
                                "(" + str(demoIndex) + "/" + str(len(toDownload)) + ") " + toDownloadServerNames[
                                    demoIndex] + "/" + os.path.basename(demoUrl))
                urllib.urlretrieve(demoUrl, "./demos/" + os.path.basename(demoUrl))
            update_progress(1,"")
            sys.stdout.flush()
        with safe_open_w("./servers.json") as f:
            f.write(newServerList.toJSON())
        print "All PRDemos from servers downloaded."


StatsParser()
