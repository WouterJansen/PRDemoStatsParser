import sys
import struct
import zlib
import cStringIO
import json
import os
import time


# Helper function to return a null terminated string from pos in buffer
def getstring(stream):
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
            index = unpack(stream, "h")
            if index >= 0:
                (name, seat) = unpack(stream, "sb")
                values.append((index, name, seat))
            else:
                values.append(index)

        elif fmt[i] == 's':
            string = getstring(stream)
            values.append(string)
        else:
            size = struct.calcsize(fmt[i])
            values.append(struct.unpack("<" + fmt[i], stream.read(size))[0])

    if len(values) == 1:
        return values[0]
    return values


class Flag(object):

    def __init__(self, cpid, x, y, z, radius):
        self.cpid = cpid
        self.x = x
        self.y = y
        self.z = z
        self.radius = radius

    def printFlag(self):
        print "Flag CPID:" + str(self.cpid) + ", at: " + str(self.x) + "," + str(self.y) + "," + str(self.z) + " with radius " + str(self.radius)


class ParsedDemo(object):

    def __init__(self, date=0, map=0, gameMode=0, layer=0, duration=0, playerCount=0, ticketsTeam1=0, ticketsTeam2=0, flags=[]):
        self.map = map
        self.date = date
        self.gameMode = gameMode
        self.layer = layer
        self.duration = duration
        self.playerCount = playerCount
        self.ticketsTeam1 = ticketsTeam1
        self.ticketsTeam2 = ticketsTeam2
        self.flags = flags

    def setData(self, date, map, gameMode, layer, duration, playerCount, ticketsTeam1, ticketsTeam2, flags):
        self.date = date
        self.map = map
        self.gameMode = gameMode
        self.layer = layer
        self.duration = duration
        self.playerCount = playerCount
        self.ticketsTeam1 = ticketsTeam1
        self.ticketsTeam2 = ticketsTeam2
        self.flags = flags

    def printData(self):
        print "Map: " + self.map + " " + self.gameMode + " " + str(
            self.layer) + " played on " + time.strftime('%Y-%m-%d %H:%M:%S',
                                                           time.localtime(self.date))
        print "Duration:" + str(self.duration) + ", PlayerCount:" + str(self.playerCount) + ", Tickets: " + str(self.ticketsTeam1) + "," + str(self.ticketsTeam2)
        for flag in self.flags:
            flag.printFlag()

    def getFlagId(self):
        flagCPIDs = []
        for flag in self.flags:
            flagCPIDs.append(flag.cpid)
        return " ".join(str(x) for x in flagCPIDs)

class Map(object):


    def __init__(self):
        self.gameModes = {}
        self.timesPlayed = 0
        self.averageDuration = 0
        self.averageTicketsTeam1 = 0
        self.averageTicketsTeam2 = 0
        self.winsTeam1 = 0
        self.winsTeam2 = 0
        self.draws = 0

class GameMode(object):


    def __init__(self):
        self.layers = {}
        self.timesPlayed = 0
        self.averageDuration = 0
        self.averageTicketsTeam1 = 0
        self.averageTicketsTeam2 = 0
        self.winsTeam1 = 0
        self.winsTeam2 = 0
        self.draws = 0

class Layer(object):


    def __init__(self):
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

class demoParser:
    def __init__(self, filename):
        compressedFile = open("./demos/" + filename, 'rb')
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
        sys.stdout.flush()
        sys.stdout.write("\rParsing " + filename + " ...")
        # print "Parsing " + filename + " ..."
        # parse the first few until serverDetails one to get map info
        while self.runMessage != 0x00:
            pass

        self.runToEnd()

        try:
            self.parsedDemo.setData(self.date, self.mapName, self.mapGamemode, self.mapLayer, self.timePlayed, self.players,
                                      self.ticket1, self.ticket2, self.flags)
            self.parsedDemo.completed = True
        except:
            pass
    def getParsedDemo(self):
        return self.parsedDemo

    # Returns the message type
    @property
    def runMessage(self):
        # Check if end of file
        tmp = self.stream.read(2)
        if len(tmp) != 2:
            return 0x99

        # Get 2 bytes of message length
        messageLength = struct.unpack("H", tmp)[0]

        startPos = self.stream.tell()
        messageType = struct.unpack("B", self.stream.read(1))[0]

        if messageType == 0x00:  # server details
            values = unpack(self.stream, "IfssBHHssBssIHH")
            self.mapName = values[7]
            self.mapGamemode = values[8]
            self.mapLayer = values[9]
            self.date = values[12]

        elif messageType == 0x52:  # tickets team 1
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "H")
                if values < 9000:
                    self.ticket1 = values

        elif messageType == 0x53:  # tickets team 2
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "H")
                if values < 9000:
                    self.ticket2 = values

        elif messageType == 0xf1:  # tick
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "B")
                self.timePlayed = self.timePlayed + values * 0.04

        elif messageType == 0x11:  # add player (ID, name, hash, IP)
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "Bsss")
                self.players = self.players + 1

        elif messageType == 0x12:  # remove player (ID)
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "B")
                self.players = self.players - 1

        elif messageType == 0x41:  # flaglist
            while self.stream.tell() - startPos != messageLength:
                values = unpack(self.stream, "HBHHHH")
                self.flags.append(Flag(values[0], values[2], values[3], values[4], values[5]))


        else:
            self.stream.read(messageLength - 1)
        return messageType

    # Returns when tick or round end recieved.
    # Returns false when roundend message recieved
    def runTick(self):
        while True:
            messageType = self.runMessage
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
    maps = {}

    def __init__(self):
        print "Parsing PRDemos..."
        self.dataAggragation()
        sys.stdout.flush()
        sys.stdout.write("\rParsing PRDemos complete.")
        print "\nCalculating Statistics..."
        self.statsCalc()
        print "Statistics Calculated."
        # for filename in os.listdir("./mapdata/"):
        #     if filename.endswith(".json"):
        #         os.remove("./mapdata/" + filename)

        #mapList = []
        # for filename in os.listdir("./mapdata/"):
        #     mapList.append(os.path.splitext(filename)[0])
        #     continue
        # if not os.path.isfile("./mapdata/maplist.json"):
        #     with open("./mapdata/maplist.json", 'w') as outfile:
        #         json.dump(mapList, outfile)

    def statsCalc(self):
        for mapname,map in self.maps.iteritems():
            mapTotalTickets1 = 0
            mapTotalTickets2 = 0
            mapTotalDuration = 0
            for gamemodename,gamemode in map.gameModes.iteritems():
                gamemodeTotalTickets1 = 0
                gamemodeTotalTickets2 = 0
                gamemodeTotalDuration = 0
                for layername,layer in gamemode.layers.iteritems():
                    layerTotalTickets1 = 0
                    layerTotalTickets2 = 0
                    layerTotalDuration = 0
                    for index,route in enumerate(layer.routes, start=0):
                        self.maps[mapname].gameModes[gamemodename].layers[layername].routes[index].timesPlayed = len(route.roundsPlayed)
                        self.maps[mapname].gameModes[gamemodename].layers[layername].timesPlayed += len(route.roundsPlayed)
                        self.maps[mapname].gameModes[gamemodename].timesPlayed += len(route.roundsPlayed)
                        self.maps[mapname].timesPlayed += len(route.roundsPlayed)
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
                        self.maps[mapname].gameModes[gamemodename].layers[layername].routes[index].averageTicketsTeam1 = routeTotalTickets1 / len(route.roundsPlayed)
                        self.maps[mapname].gameModes[gamemodename].layers[layername].routes[index].averageTicketsTeam2 = routeTotalTickets2 / len(route.roundsPlayed)
                        self.maps[mapname].gameModes[gamemodename].layers[layername].routes[index].averageDuration = routeTotalDuration / len(route.roundsPlayed)
                        self.maps[mapname].gameModes[gamemodename].layers[layername].routes[index].winsTeam1 = winsTeam1
                        self.maps[mapname].gameModes[gamemodename].layers[layername].routes[index].winsTeam2 = winsTeam2
                        self.maps[mapname].gameModes[gamemodename].layers[layername].routes[index].draws += draws
                        self.maps[mapname].gameModes[gamemodename].layers[layername].winsTeam1 += winsTeam1
                        self.maps[mapname].gameModes[gamemodename].layers[layername].winsTeam2 += winsTeam2
                        self.maps[mapname].gameModes[gamemodename].layers[layername].draws += draws
                        self.maps[mapname].gameModes[gamemodename].winsTeam1 += winsTeam1
                        self.maps[mapname].gameModes[gamemodename].winsTeam2 += winsTeam2
                        self.maps[mapname].gameModes[gamemodename].draws += draws
                        self.maps[mapname].winsTeam1 += winsTeam1
                        self.maps[mapname].winsTeam2 += winsTeam2
                        self.maps[mapname].draws += draws
                    self.maps[mapname].gameModes[gamemodename].layers[layername].averageTicketsTeam1 = layerTotalTickets1 / self.maps[mapname].gameModes[gamemodename].layers[layername].timesPlayed
                    self.maps[mapname].gameModes[gamemodename].layers[layername].averageTicketsTeam2 = layerTotalTickets2 / self.maps[mapname].gameModes[gamemodename].layers[layername].timesPlayed
                    self.maps[mapname].gameModes[gamemodename].layers[layername].averageDuration = layerTotalDuration / self.maps[mapname].gameModes[gamemodename].layers[layername].timesPlayed
                self.maps[mapname].gameModes[gamemodename].averageTicketsTeam1 = gamemodeTotalTickets1 / self.maps[mapname].gameModes[gamemodename].timesPlayed
                self.maps[mapname].gameModes[gamemodename].averageTicketsTeam2 = gamemodeTotalTickets2 / self.maps[mapname].gameModes[gamemodename].timesPlayed
                self.maps[mapname].gameModes[gamemodename].averageDuration = gamemodeTotalDuration / self.maps[mapname].gameModes[gamemodename].timesPlayed
            self.maps[mapname].averageTicketsTeam1 = mapTotalTickets1 / self.maps[mapname].timesPlayed
            self.maps[mapname].averageTicketsTeam2 = mapTotalTickets2 / self.maps[mapname].timesPlayed
            self.maps[mapname].averageDuration = mapTotalDuration / self.maps[mapname].timesPlayed
    def dataAggragation(self):
        for filename in os.listdir("./demos/"):
            if filename.endswith(".PRdemo"):
                parsedDemo = demoParser(filename).getParsedDemo()
                if parsedDemo.map != 0 and parsedDemo.playerCount > 80:
                    if parsedDemo.map in self.maps:
                        if parsedDemo.gameMode in self.maps[parsedDemo.map].gameModes:
                            if parsedDemo.layer in self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers:
                                found = False
                                for index, route in enumerate(
                                        self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                                            parsedDemo.layer].routes, start=0):
                                    if route.id == parsedDemo.getFlagId():
                                        self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                                            parsedDemo.layer].routes[index].roundsPlayed.append(parsedDemo)
                                        found = True
                                if found == False:
                                    self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                                        parsedDemo.layer].routes.append(Route(parsedDemo.getFlagId()))
                                    self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                                        parsedDemo.layer].routes[-1].roundsPlayed.append(parsedDemo)
                            else:
                                self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                                    parsedDemo.layer] = Layer()
                                self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                                    parsedDemo.layer].routes.append(Route(parsedDemo.getFlagId()))
                                self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                                    parsedDemo.layer].routes[0].roundsPlayed.append(parsedDemo)

                        else:
                            self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode] = GameMode()
                            self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                                parsedDemo.layer] = Layer()
                            self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                                parsedDemo.layer].routes.append(Route(parsedDemo.getFlagId()))
                            self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                                parsedDemo.layer].routes[0].roundsPlayed.append(parsedDemo)
                    else:
                        self.maps[parsedDemo.map] = Map()
                        self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode] = GameMode()
                        self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[parsedDemo.layer] = Layer()
                        self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                            parsedDemo.layer].routes.append(Route(parsedDemo.getFlagId()))
                        self.maps[parsedDemo.map].gameModes[parsedDemo.gameMode].layers[
                            parsedDemo.layer].routes[0].roundsPlayed.append(parsedDemo)

StatsParser()
