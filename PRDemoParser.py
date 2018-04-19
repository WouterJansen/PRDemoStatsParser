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
import multiprocessing
from bs4 import BeautifulSoup
import requests
import urllib
import numpy as np
import time
from shutil import copyfile
import urlparse
from pyheatmap.heatmap import HeatMap
###############################
#           HELPERS           #
###############################

# Helper functions to turn json files into namedtuple
def _json_object_hook(d): return namedtuple('X', d.keys())(*d.values())
def json2obj(data): return json.loads(data, object_hook=_json_object_hook)


def getDemoName(demoUrl):
    if "file=" in demoUrl:
       return demoUrl.split("file=")[1]
    else:
        return os.path.basename(demoUrl)

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
        files.sort()
        for filename in files:
            yield os.path.abspath(os.path.join(dirpath, filename))

# Helper function to show progress bar
def update_progress(currentCount,totalCount):
    barLength = 20
    progress = float(currentCount) / totalCount
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
    block = int(round(barLength*progress))
    text = "\r[{0}] {1}% {2}".format( "#"*block + "-"*(barLength-block), round(progress*100,2), " (" + str(currentCount) + "/" + str(totalCount) + ")")
    sys.stdout.write(text)
    sys.stdout.flush()

# Helper function that is used by multiprocessing to start a worker to parse a PRDemo
def parseNewDemo(filepath):
    parsedDemo = demoParser(filepath).getParsedDemo()
    return parsedDemo

#Find the map scale found in /input/maps.json. Used for correctly aggragate positions of players
#to heatmap data.
def findScale(mapName):
    try:
        with open("./input/maps.json", 'r') as f:
            mapInfoData = f.read()
            mapInfo = json2obj(mapInfoData)
            if hasattr(mapInfo, mapName):
                return getattr(mapInfo, mapName).scale
            else:
                return 0
    except:
        return 0


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
                 flags=[],heatMap = None):
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
        self.heatMap = heatMap

    def setData(self, version, date, map, gameMode, layer, duration, playerCount, ticketsTeam1, ticketsTeam2, flags,heatMap):
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
        self.heatMap = heatMap

    # TODO Implement SGID method
    # Create ID of flag route based on CPID list (placeholder until SGID is available to calculate route ID)
    def getFlagId(self):
        flagCPIDs = []
        for flag in self.flags:
            flagCPIDs.append(flag.cpid)
        flagCPIDs.sort()
        return ("Route " + ", ".join(str(x) for x in flagCPIDs)).strip()


class ServerList(object):

    def __init__(self,prpath,webpath):
        self.date = str(datetime.datetime.now())
        if prpath != None:
            self.prpath = prpath
        if webpath != None:
            self.webpath = webpath
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
        self.date = str(datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"))

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

    def __init__(self, id, updated):
        self.id = id
        self.roundsPlayed = []
        self.timesPlayed = 0
        self.averageDuration = 0
        self.averageTicketsTeam1 = 0
        self.averageTicketsTeam2 = 0
        self.winsTeam1 = 0
        self.winsTeam2 = 0
        self.draws = 0
        self.heatMap = 0
        self.updated = updated

class Player:
    def __init__(self):
        self.isalive = 0

    def __setitem__(self, key, value):
        self.__dict__[key] = value

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

        self.stream = cStringIO.StringIO(buffer)
        self.length = len(buffer)

        self.playerCount = 0
        self.timePlayed = 0
        self.flags = []
        self.parsedDemo = ParsedDemo()
        self.scale = 0
        self.playerDict = {}
        self.PLAYERFLAGS = [
            ('team', 1, 'B'),
            ('squad', 2, 'B'),
            ('vehicle', 4, 'v'),
            ('health', 8, 'b'),
            ('score', 16, 'h'),
            ('twscore', 32, 'h'),
            ('kills', 64, 'h'),
            ('deaths', 256, 'h'),
            ('ping', 512, 'h'),
            ('isalive', 2048, 'B'),
            ('isjoining', 4096, 'B'),
            ('pos', 8192, 'hhh'),
            ('rot', 16384, 'h'),
            ('kit', 32768, 's'),
        ]
        self.heatMap = np.zeros(shape=(512,512))
        timeoutindex = 0
        # parse the first few until serverDetails one to get map info
        while self.runMessage() != 0x00:
            if timeoutindex == 10000:
                break
            timeoutindex += 1
            pass
        self.runToEnd()

        # create ParsedDemo object and set it to complete if it was able to get all data
        try:
            self.parsedDemo.setData(self.version, self.date, self.mapName, self.mapGamemode, self.mapLayer, self.timePlayed / 60,
                                    self.playerCount,
                                    self.ticket1, self.ticket2, self.flags,self.heatMap.astype(int))
            self.parsedDemo.completed = True
        except Exception, e:
            pass

    def getParsedDemo(self):
        return self.parsedDemo

    #Find the next message and analyze it.
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
        except Exception, e:
            return 0x99

        if messageType == 0x00:  # server details
            values = unpack(self.stream, "IfssBHHssBssIHH")
            if values == -1:
                return 0x99
            version = values[3].split(']')[0].split(' ')
            self.version = version[1]
            self.mapName = values[7]
            self.scale = findScale(self.mapName)
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
                if values == -1:
                    return 0x99
                if values < 9000:
                    self.ticket1 = values
                else:
                    self.ticket1 = 0

        elif messageType == 0x53:  # tickets team 2
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "H")
                if values == -1:
                    return 0x99
                if values < 9000:
                    self.ticket2 = values
                else:
                    self.ticket2 = 0

        elif messageType == 0xf1:  # tick
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "B")
                if values == -1:
                    return 0x99
                self.timePlayed = self.timePlayed + values * 0.04

        elif messageType == 0x10 and self.scale != 0:  # update player
            while self.stream.tell() - startPos != messageLength:
                flags = unpack(self.stream, "H")
                try:
                    p = self.playerDict[unpack(self.stream, "B")]
                    for tuple in self.PLAYERFLAGS:
                        field, bit, fmt = tuple
                        if flags & bit:
                            p[field] = unpack(self.stream, fmt)
                            if field == "pos":
                                if p.isalive:
                                    if p.pos[0] < 256 * self.scale * 2 and p.pos[0] > -256 * self.scale * 2 and \
                                            p.pos[2] < 256 * self.scale * 2 and p.pos[2] > -256 * self.scale * 2:
                                        x = int(round(p.pos[0] / (self.scale * 4) + 128))
                                        y = int(round(p.pos[2] / (self.scale * -4) + 128))
                                        self.heatMap[(x - 1) * 2, (y - 1) * 2] += 1
                except:
                    return 0x99

        elif messageType == 0x11:  # add player
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "Bsss")
                if values == -1:
                    return 0x99
                p = Player()
                p.id = values[0]
                p.name = values[1]
                p.hash = values[2]
                p.ip = values[3]
                self.playerDict[values[0]] = p
                self.playerCount += 1

        elif messageType == 0x12:  # remove player
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "B")
                if values == -1:
                    return 0x99
                del self.playerDict[values]
                self.playerCount -= 1

        elif messageType == 0x41:  # flaglist
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "HBHHHH")
                if values == -1:
                    return 0x99
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
        self.generateHeatMaps()
        self.statsCalc()
        self.createMapList()
        self.copyData()

    # Calculate statistics such as times played and average tickets based on data
    def statsCalc(self):
        if len(self.versions) != 0:
            print "Calculating & exporting statistics..."
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
                                if gameMode.name != "Co-Operative":
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
                                    if gameMode.name != "Co-Operative":
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
                                if gameMode.name != "Co-Operative":
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
                                if gameMode.name != "Co-Operative":
                                    self.versions[versionname][mapname].averageTicketsTeam1 = mapTotalTickets1 / self.versions[versionname][mapname].timesPlayed
                                    self.versions[versionname][mapname].averageTicketsTeam2 = mapTotalTickets2 / self.versions[versionname][mapname].timesPlayed
                                    self.versions[versionname][mapname].averageDuration = mapTotalDuration / self.versions[versionname][mapname].timesPlayed

            for versionname, version in self.versions.iteritems():
                for mapname, map in version.iteritems():
                    # Export the statistics to the /maps/mapname/statistics.json files but first remove large heatmap data.
                    with safe_open_w("./data/" + versionname + "/" + mapname + "/statistics.json") as f:
                        for gameModeIndex, gameMode in enumerate(map.gameModes, start=0):
                            for layerIndex, layer in enumerate(gameMode.layers, start=0):
                                for routeIndex, route in enumerate(layer.routes, start=0):
                                    for demoIndex, demo in enumerate(route.roundsPlayed, start=0):
                                        del self.versions[versionname][mapname].gameModes[gameModeIndex].layers[
                                            layerIndex].routes[routeIndex].roundsPlayed[demoIndex].heatMap
                        f.write(map.toJSON())
            print "Calculation & export of statistics complete."
        else:
            print "Data to calculate and export statistics not found."

    # Map the parsedDemo to the correct structure in the statistics based on Map,GameMode,Layer,Route
    def demoToData(self,parsedDemo,updated):
        if parsedDemo.map != 0 and ((parsedDemo.gameMode == "Co-Operative" and parsedDemo.playerCount > 2) or (
                parsedDemo.gameMode != "Co-Operative" and parsedDemo.gameMode != "Skirmish" and parsedDemo.playerCount > 64) or (
                                            parsedDemo.gameMode == "Skirmish" and parsedDemo.playerCount > 8)):
            if parsedDemo.version in self.versions:
                if parsedDemo.map in self.versions[parsedDemo.version]:
                    gameModeFound = False
                    for gameModeIndex, gameMode in enumerate(self.versions[parsedDemo.version][parsedDemo.map].gameModes,
                                                             start=0):
                        if gameMode.name == parsedDemo.gameMode:
                            layerFound = False
                            for layerIndex, layer in enumerate(
                                    self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers,
                                    start=0):
                                if layer.name == parsedDemo.layer:
                                    routeFound = False
                                    for routeIndex, route in enumerate(
                                            self.versions[parsedDemo.version][parsedDemo.map].gameModes[
                                                gameModeIndex].layers[
                                                layerIndex].routes, start=0):
                                        if route.id == parsedDemo.getFlagId():
                                            self.versions[parsedDemo.version][parsedDemo.map].gameModes[
                                                gameModeIndex].layers[
                                                layerIndex].routes[routeIndex].roundsPlayed.append(parsedDemo)
                                            if updated:
                                                self.versions[parsedDemo.version][parsedDemo.map].gameModes[
                                                    gameModeIndex].layers[
                                                    layerIndex].routes[routeIndex].updated = True
                                            routeFound = True
                                    if not routeFound:
                                        self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers[
                                            layerIndex].routes.append(Route(parsedDemo.getFlagId(),updated))
                                        self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers[
                                            layerIndex].routes[-1].roundsPlayed.append(parsedDemo)
                                layerFound = True
                            if not layerFound:
                                self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers.append(
                                    Layer(parsedDemo.layer))
                                self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers[
                                    -1].routes.append(
                                    Route(parsedDemo.getFlagId(),updated))
                                self.versions[parsedDemo.version][parsedDemo.map].gameModes[gameModeIndex].layers[-1].routes[
                                    0].roundsPlayed.append(
                                    parsedDemo)
                            gameModeFound = True
                    if not gameModeFound:
                        self.versions[parsedDemo.version][parsedDemo.map].gameModes.append(GameMode(parsedDemo.gameMode))
                        self.versions[parsedDemo.version][parsedDemo.map].gameModes[-1].layers.append(
                            Layer(parsedDemo.layer))
                        self.versions[parsedDemo.version][parsedDemo.map].gameModes[-1].layers[0].routes.append(
                            Route(parsedDemo.getFlagId(),updated))
                        self.versions[parsedDemo.version][parsedDemo.map].gameModes[-1].layers[0].routes[
                            0].roundsPlayed.append(parsedDemo)
                else:
                    self.versions[parsedDemo.version][parsedDemo.map] = Map(parsedDemo.map)
                    self.versions[parsedDemo.version][parsedDemo.map].gameModes.append(GameMode(parsedDemo.gameMode))
                    self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers.append(Layer(parsedDemo.layer))
                    self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers[0].routes.append(
                        Route(parsedDemo.getFlagId(),updated))
                    self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers[0].routes[0].roundsPlayed.append(
                        parsedDemo)
            else:
                self.versions[parsedDemo.version] = {}
                self.versions[parsedDemo.version][parsedDemo.map] = Map(parsedDemo.map)
                self.versions[parsedDemo.version][parsedDemo.map].gameModes.append(GameMode(parsedDemo.gameMode))
                self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers.append(
                    Layer(parsedDemo.layer))
                self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers[0].routes.append(
                    Route(parsedDemo.getFlagId(),updated))
                self.versions[parsedDemo.version][parsedDemo.map].gameModes[0].layers[0].routes[
                    0].roundsPlayed.append(parsedDemo)


    # Parse all PRdemo files in the demos folder. It also removes the files after parsing to avoid duplicate entries.
    # This uses multiprocessing to devide the work among the cores.
    def dataAggragation(self):
        demosToParseCount = 0
        for filepath in walkdir("./demos"):
            demosToParseCount += 1
        filesToParse = []
        if demosToParseCount != 0:
            for index, filepath in enumerate(walkdir("./demos"), start=0):
                head, tail = os.path.split(filepath)
                if os.stat(filepath).st_size > 10000:
                    filesToParse.append(filepath)
            if len(filesToParse) != 0:
                print "Parsing valid new PRDemos..."
                pool = multiprocessing.Pool(multiprocessing.cpu_count()-1)
                resultingParsedDemos = pool.map_async(parseNewDemo, filesToParse,chunksize=1)
                pool.close()
                while (True):
                    update_progress(len(filesToParse) - resultingParsedDemos._number_left,len(filesToParse))
                    time.sleep(0.5)
                    if (resultingParsedDemos.ready()): break
                resultingParsedDemos.wait()
                update_progress(len(filesToParse), len(filesToParse))
                resultingParsedDemos = resultingParsedDemos.get()
                for parsedDemo in resultingParsedDemos:
                    self.demoToData(parsedDemo,True)
                filelist = [f for f in os.listdir("./demos") if f.endswith(".PRdemo")]
                for f in filelist:
                    os.remove(os.path.join("./demos", f))
                print "\nParsing of new PRDemos(" + str(demosToParseCount) + ") complete."
            else:
                print "There are no valid new PRDemos to parse."
        else:
            print "There are no valid new PRDemos to parse."


    # Create maplist.json with basic map statistics for map list overview
    def createMapList(self):
        mapList = MapList()
        foundMapNames = False
        try:
            with open("./input/maps.json", 'r') as f:
                mapNames = json2obj(f.read())
                foundMapNames = True
        except:
            print "Couldn't find /input/maps.json to generate display names from."
        if len(self.versions) > 0:
            print "Creating maplist..."
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
                                mapObject.displayName = getattr(mapNames,mapname).displayName
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
            with safe_open_w("./data/maplist.json") as f:
                f.write(mapList.toJSON())
            print "Created maplist."
        else:
            print "There is no data to create maplist from."

    # Import existing data.json files of each map and gets the parsedDemos to be able to re-calculate the statistics
    def importStats(self):
        totalStatisticsCount = 0
        for filepath in walkdir("./data"):
            if fnmatch(filepath, "*statistics.json") is True:
                totalStatisticsCount += 1
        if totalStatisticsCount >= 1:
            print "Importing existing statistics..."
            for index, filepath in enumerate(walkdir("./data"), start=0):
                if fnmatch(filepath, "*statistics.json") is True:
                    update_progress(index,totalStatisticsCount)
                    with open(filepath, 'r') as f:
                        importedMapStatistics = json2obj(f.read())
                        for gamemode in importedMapStatistics.gameModes:
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
                                        self.demoToData(newDemo,False)
                    update_progress(totalStatisticsCount,totalStatisticsCount)

            print "\nImport of existing statistics(" + str(totalStatisticsCount) + ") complete."
        else:
            print "Existing statistics not found."

    #Download new demos from servers defined in /input/config.json. Every demo that is downloaded is appended
    #to the 'demos' list in the json to avoid duplicates.
    def downloadDemos(self):
        try:
            with open('./input/config.json', 'r') as f:
                if not os.path.exists("./demos"):
                    os.makedirs("./demos")
                config = json2obj(f.read())
                demosToDownload = []
                toDownloadServerNames = []
                serverNameList = []
                if hasattr(config, 'prpath') and hasattr(config, 'webpath'):
                    newServerConfig = ServerList(config.prpath,config.webpath)
                elif hasattr(config, 'prpath'):
                    newServerConfig = ServerList(config.prpath, None)
                elif hasattr(config, 'webpath'):
                    newServerConfig = ServerList(None, config.webpath)
                else:
                    newServerConfig = ServerList(None, None)
                for serverIndex, server in enumerate(config.servers, start=0):
                    demoDownloadLinks = []
                    demos = server.demos
                    for linkIndex, link in enumerate(server.links, start=0):
                        demoDownloadLinks.append(link)
                        if fnmatch(link, "*.json"):
                            crawlers = json2obj(urllib.urlopen(link).read())
                            for crawler in crawlers:
                                for demoUrlIndex, demoUrl in enumerate(crawler.Trackers, start=0):
                                    if getDemoName(demoUrl) not in server.demos:
                                        if server.name not in serverNameList:
                                            serverNameList.append(server.name)
                                        demosToDownload.append(demoUrl)
                                        toDownloadServerNames.append(server.name)
                                        demos.append(getDemoName(demoUrl))
                        else:
                            soup = BeautifulSoup(requests.get(link).text, 'html.parser')
                            for demoUrl in [link + node.get('href') for node in soup.find_all('a') if
                                            node.get('href').endswith('PRdemo')]:
                                if getDemoName(demoUrl) not in server.demos:
                                    if server.name not in serverNameList:
                                        serverNameList.append(server.name)
                                    demosToDownload.append(demoUrl)
                                    toDownloadServerNames.append(server.name)
                                    demos.append(getDemoName(demoUrl))
                    newServerConfig.servers.append(Server(server.name, demoDownloadLinks, demos))
                if len(demosToDownload) != 0:
                    print "Downloading available PRDemos from servers(" + ','.join(serverNameList) + ")..."
                    for demoIndex, demoUrl in enumerate(demosToDownload, start=0):
                        update_progress(demoIndex,len(demosToDownload))
                        urllib.urlretrieve(demoUrl, "./demos/" + getDemoName(demoUrl))
                        # update_progress(demoIndex,len(demosToDownload))
                    update_progress(len(demosToDownload), len(demosToDownload))
                    print "\nAll available PRDemos from servers("+ str(len(demosToDownload)) + ") downloaded."
                else:
                    print "There are no new PRDemos to download."
                with safe_open_w("./input/config.json") as f:
                    f.write(newServerConfig.toJSON())
        except :
            print "/input/config.json file not found. Can't download demos automatically."

    #Generate heatmap data based on player locations. Includes importing of existing data through loading in
    #existing numpy matrixes (.npy) files found in the data folder for each route.
    def generateHeatMaps(self):
        totalHeatMapCount = 0
        for versionname,version in self.versions.iteritems():
            for mapname, map in version.iteritems():
                totalHeatMapCount += 1
                for gameModeIndex, gameMode in enumerate(map.gameModes, start=0):
                    totalHeatMapCount += 1
                    for layerIndex, layer in enumerate(gameMode.layers, start=0):
                        totalHeatMapCount += 1
                        for routeIndex, route in enumerate(layer.routes, start=0):
                            totalHeatMapCount += 1
        currentHeatMapCount = 1
        if totalHeatMapCount != 0:
            print "Generating heatmaps..."
            for versionname,version in self.versions.iteritems():
                for mapname, map in version.iteritems():
                    update_progress(currentHeatMapCount,totalHeatMapCount)
                    mapHeatMapData = []
                    gameModeChanged = False
                    for gameModeIndex, gameMode in enumerate(map.gameModes, start=0):
                        update_progress(currentHeatMapCount, totalHeatMapCount)
                        gameModeHeatMapData = []
                        layerChanged = False
                        for layerIndex, layer in enumerate(gameMode.layers, start=0):
                            update_progress(currentHeatMapCount, totalHeatMapCount)
                            layerHeatMapData = []
                            routeChanged = False
                            for routeIndex, route in enumerate(layer.routes, start=0):
                                update_progress(currentHeatMapCount, totalHeatMapCount)
                                if route.updated:
                                    routeChanged = True
                                    routeHeatMapMatrix = np.zeros(shape=(512,512))
                                    routeHeatMapName = "./data/" + versionname + "/" + mapname + "/" + "combinedmovement_" + gameMode.name + "_" + layer.name + "_" + route.id
                                    try:
                                        importedRouteHeatMap = np.load(str(routeHeatMapName + ".npy"))
                                        routeHeatMapMatrix = routeHeatMapMatrix + importedRouteHeatMap
                                    except Exception, e:
                                        pass
                                    for parsedDemo in route.roundsPlayed:
                                        if type(parsedDemo.heatMap) is not type(None):
                                            routeHeatMapMatrix = routeHeatMapMatrix + parsedDemo.heatMap
                                    if not os.path.exists("./data/" + versionname + "/" + mapname):
                                        os.makedirs("./data/" + versionname + "/" + mapname)
                                    np.save(routeHeatMapName,routeHeatMapMatrix)
                                    routeHeatMapData = []
                                    for ix, iy in np.ndindex(routeHeatMapMatrix.shape):
                                        for count in range(0,int(routeHeatMapMatrix[ix,iy])):
                                            routeHeatMapData.append([ix, iy])
                                    HeatMap(data=routeHeatMapData,width=512,height=512).heatmap(save_as=routeHeatMapName + ".png")
                                    HeatMap()
                                    layerHeatMapData.extend(routeHeatMapData)
                                currentHeatMapCount += 1
                            if routeChanged:
                                layerChanged = True
                                layerHeatMapFileName = "./data/" + versionname + "/" + mapname + "/" + "combinedmovement_" + gameMode.name + "_" + layer.name + ".png"
                                if len(layer.routes) > 1:
                                    HeatMap(data=layerHeatMapData,width=512,height=512).heatmap(save_as=layerHeatMapFileName)
                                else:
                                    routeHeatMapFileName = "./data/" + versionname + "/" + mapname + "/" + "combinedmovement_" + gameMode.name + "_" + layer.name + "_" + layer.routes[0].id + ".png"
                                    copyfile(routeHeatMapFileName,layerHeatMapFileName)
                                gameModeHeatMapData.extend(layerHeatMapData)
                            currentHeatMapCount += 1
                        if layerChanged:
                            gameModeChanged = True
                            gameModeHeatMapFileName = "./data/" + versionname + "/" + mapname + "/" + "combinedmovement_" + gameMode.name + ".png"
                            if len(gameMode.layers) > 1:
                                HeatMap(data=gameModeHeatMapData,width=512,height=512).heatmap(save_as=gameModeHeatMapFileName)
                            else:
                                layerHeatMapFileName = "./data/" + versionname + "/" + mapname + "/" + "combinedmovement_" + gameMode.name + "_" + gameMode.layers[0].name + ".png"
                                copyfile(layerHeatMapFileName, gameModeHeatMapFileName)
                            mapHeatMapData.extend(gameModeHeatMapData)
                        currentHeatMapCount += 1
                    if gameModeChanged:
                        mapHeatMapFileName = "./data/" + versionname + "/" + mapname + "/" + "combinedmovement" + ".png"
                        if len(map.gameModes) > 1:
                            HeatMap(data=mapHeatMapData,width=512,height=512).heatmap(save_as=mapHeatMapFileName)
                        else:
                            gameModeHeatMapFileName = "./data/" + versionname + "/" + mapname + "/" + "combinedmovement_" + map.gameModes[0].name + ".png"
                            copyfile(gameModeHeatMapFileName, mapHeatMapFileName)
                    currentHeatMapCount += 1
            update_progress(totalHeatMapCount, totalHeatMapCount)
            print "\nAll heatmaps(" + str(totalHeatMapCount) +") generated."
        else:
            print "There is no data to generate heatmaps from."


    def copyData(self):
        imagescount = 0
        for index, filepath in enumerate(walkdir("./input"), start=0):
            if fnmatch(filepath, "*.jpg"):
                imagescount += 1
        if imagescount > 0:
            print "Copying images to data folder..."
            if not os.path.exists("./data/images"):
                os.makedirs("./data/images")
            for index, filepath in enumerate(walkdir("./input"), start=0):
                head, tail = os.path.split(filepath)
                if fnmatch(filepath, "*.jpg"):
                    copyfile(filepath, "./data/images/" + tail)
            print "All images copied to data folder."
        else:
            print "No images found to copy."
        try:
            print "Copying data to web folder..."
            with open('./input/config.json', 'r') as f:
                webPath = json2obj(f.read()).webpath
                for index, filepath in enumerate(walkdir("./data"), start=0):
                    head, tail = os.path.split(filepath)
                    if fnmatch(filepath, "*.npy") is False:
                        if not os.path.exists(webPath + "/data" + head.split("data")[1].replace("\\","/")):
                            os.makedirs(webPath + "/data" + head.split("data")[1].replace("\\","/"))
                        copyfile(filepath, webPath + "/data" + head.split("data")[1].replace("\\","/") + "/" + tail)
            print "Data copied to web folder."
        except:
            print "Web folder path not defined in /input/config.json. Can't copy data."


if __name__ == '__main__':
    StatsParser()