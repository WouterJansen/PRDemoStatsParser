import sys
import os
from collections import namedtuple

from PIL import Image
from PIL import ImageEnhance
import json
import codecs

modPath = ""
levelsPath = ""
localizationPath= ""

# Helper functions to turn json files into namedtuple
def _json_object_hook(d): return namedtuple('X', d.keys())(*d.values())
def json2obj(data): return json.loads(data, object_hook=_json_object_hook)


def get_immediate_subdirectories(a_dir):
    return [name for name in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, name))]

def generateMinimaps():
    print "Generating minimaps..."
    if not os.path.exists("./input"):
        os.makedirs("./input")
    maps =  get_immediate_subdirectories(levelsPath)
    for map in maps:
        if map != '.svn':
            try:
                img = Image.open(levelsPath + "/" + map + "/hud/minimap/original.png")
                converter = ImageEnhance.Color(img)
                img_lowerSaturation = converter.enhance(0.8)
                im_darker = img_lowerSaturation.point(lambda p: p * 0.7)
                img_resized = im_darker.resize((512, 512),Image.ANTIALIAS)
                img_noAlpha = img_resized.convert('RGB')
                img_noAlpha.save("./input/" + map + ".jpg", 'JPEG',quality=100)
            except Exception,e :
                print "  Couldn't make minimap of " + map + ":" + str(e)
    print "All minimaps generated."

def findDisplayName(name):
    encodedText = open(localizationPath + "/english/prmaps.utxt").read()  # you should read in binary mode to get the BOM correctly
    bom = codecs.BOM_UTF16_LE  # print dir(codecs) for other encodings
    assert encodedText.startswith(bom)  # make sure the encoding is what you expect, otherwise you'll get wrong data
    encodedText = encodedText[len(bom):]  # strip away the BOM
    decodedText = encodedText.decode('utf-16le')
    combinedText = ''.join(decodedText)
    foundLine = "";
    for line in combinedText.splitlines():
        if ('HUD_LEVELNAME_' + name + " ") in line:
            foundLine = line;
    if foundLine != "":
        fixedLine = foundLine.replace('', '')
        splitLine =  fixedLine.split(name)[1].split(" ")
        wordLine = []
        for index, part in enumerate(splitLine, start=0):
            if part != "":
                wordLine.append(part)
        foundScale = findScale(name)
        if foundScale is not -1:
            return " ".join(wordLine) + " (" + str(foundScale) + "km)"
        else:
            return " ".join(wordLine) + " (?km)"
    else:
        return name

def findScale(name):
    try:
        with open(levelsPath + "/" + name + "/Heightdata.con") as f:
            lines = f.readlines()
            foundLine = ""
            for line in lines:
                if "heightmap.setScale" in line.replace("\n", ""):
                    foundLine = line.replace("\n", "")
                    break
            splitLine = foundLine.split(" ")[1].split("/")
            scale = splitLine[0]
            for line in lines:
                if "heightmap.setSize" in line.replace("\n", ""):
                    foundLine = line.replace("\n", "")
                    break
            size = foundLine.split(" ")[2]
            if int(size) * int(scale) == 1025:
                return 1
            elif int(size) * int(scale) == 1026:
                return 1
            elif int(size) * int(scale) == 2050:
                return 2
            elif int(size) * int(scale) == 4100:
                return 4
            elif int(size) * int(scale) == 8256:
                return 8
    except Exception, e:
        print "  Couldn't get scale of " + name + ":" + str(e)
        return -1

def generateJSON():
    print "Generating maps.json..."
    maplist = {}
    maps = get_immediate_subdirectories(levelsPath)
    for map in maps:
        if map != '.svn':
            maplist[map] = {}
            maplist[map]['displayName'] = findDisplayName(map)
            maplist[map]['scale'] = findScale(map)
    with open("./input/maps.json", 'w') as f:
        f.write(json.dumps(maplist,indent=4))
    print "maps.json generated"

def main():

    global modPath
    global levelsPath
    global localizationPath
    try:
        with open('./input/config.json', 'r') as f:
            configData = f.read()
            config = json2obj(configData)
            modPath = config.prpath
            levelsPath = modPath + "\levels"
            localizationPath = modPath + "\localization"
            generateJSON()
            generateMinimaps()
    except Exception, e:
        print e

main()