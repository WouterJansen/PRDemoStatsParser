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


########################################################################

class Flag(object):
    cpid = 0
    team = 0
    x = 0
    y = 0
    z = 0
    radius = 0

    def __init__(self, cpid, team, x, y, z, radius):
        self.cpid = cpid
        self.team = team
        self.x = x
        self.y = y
        self.z = z
        self.radius = radius

    def printFlag(self):
        print self.cpid
        print self.team
        print self.x
        print self.y
        print self.z
        print self.radius


class demoParser:
    def __init__(self, filename):
        try:
            compressedFile = open("./demos/" + filename, 'rb')
            compressedBuffer = compressedFile.read()
        except:
            print filename + " not found!"
            sys.exit(-2)
        ####
        compressedFile.close()

        # Try to decompress or assume its not compressed if it fails
        try:
            buffer = zlib.decompress(compressedBuffer)
        except:
            print filename + "file is probably already uncompressed."
            buffer = compressedBuffer
        ####

        self.stream = cStringIO.StringIO(buffer)
        self.length = len(buffer)
        self.players = 0
        self.timePlayed = 0
        self.flags = []

        print "Parsing " + filename + " ..."
        # parse the first few until serverDetails one to get map info
        while self.runMessage != 0x00:
            pass

        self.runToEnd()

        try:
            playedRound = {'date': self.date, "data": {}}
            playedRound["data"]['mapname'] = self.mapName
            playedRound["data"]['gamemode'] = self.mapGamemode
            playedRound["data"]['layer'] = self.mapLayer
            playedRound["data"]['tickets1'] = self.ticket1
            playedRound["data"]['tickets2'] = self.ticket2
            playedRound["data"]['duration'] = self.timePlayed
            playedRound["data"]['playercount'] = self.players
            playedRound["data"]['flags'] = {}
            for flag in self.flags:
                playedRound["data"]['flags'][flag.cpid] = {}
                playedRound["data"]['flags'][flag.cpid]["team"] = flag.team
                playedRound["data"]['flags'][flag.cpid]["x"] = flag.x
                playedRound["data"]['flags'][flag.cpid]["y"] = flag.y
                playedRound["data"]['flags'][flag.cpid]["z"] = flag.z
                playedRound["data"]['flags'][flag.cpid]["radius"] = flag.radius

            if not os.path.isfile("./mapdata/" + self.mapName + ".json"):
                with open("./mapdata/" + self.mapName + ".json", 'w') as outfile:
                    roundList = []
                    roundList.append(playedRound)
                    json.dump(roundList, outfile)
            else:
                with open("./mapdata/" + self.mapName + ".json") as feedsjson:
                    roundList = json.load(feedsjson)

                roundList.append(playedRound)
                with open("./mapdata/" + self.mapName + ".json", mode='w') as f:
                    f.write(json.dumps(roundList, indent=2))

            print "Round on " + self.mapName + " " + self.mapGamemode + " " + str(
                self.mapLayer) + " played on " + time.strftime('%Y-%m-%d %H:%M:%S',
                                                               time.localtime(self.date)) + " parsed!"
        except:
            print "Uncompleted round, skipping!"

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
                self.flags.append(Flag(values[0], values[1], values[2], values[3], values[4], values[5]))


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


for filename in os.listdir("./mapdata/"):
    if filename.endswith(".json"):
        os.remove("./mapdata/" + filename)
        continue
for filename in os.listdir("./demos/"):
    if filename.endswith(".PRdemo"):
        demoParser(filename)
        continue
