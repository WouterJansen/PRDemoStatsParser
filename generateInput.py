import sys
import os
from PIL import Image
from PIL import ImageEnhance
import json
import codecs

MODPATH = sys.argv[1]
LEVELSPATH = MODPATH + "\levels"
LOCALIZATIONPATH= MODPATH + "\localization"

def get_immediate_subdirectories(a_dir):
    return [name for name in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, name))]

def generateMinimaps():
    print "Generating minimaps..."
    if not os.path.exists("./input"):
        os.makedirs("./input")
    maps =  get_immediate_subdirectories(LEVELSPATH)
    for map in maps:
        if map != '.svn':
            try:
                img = Image.open(LEVELSPATH + "/" + map + "/hud/minimap/original.png")
                converter = ImageEnhance.Color(img)
                img_lowerSaturation = converter.enhance(0.8)
                im_darker = img_lowerSaturation.point(lambda p: p * 0.7)
                img_resized = im_darker.resize((512, 512),Image.ANTIALIAS)
                img_noAlpha = img_resized.convert('RGB')
                img_noAlpha.save("./input/" + map + ".jpg", 'JPEG',quality=100)
            except Exception,e :
                pass
    print "All minimaps generated."

def findDisplayName(name):
    encodedText = open(LOCALIZATIONPATH + "/english/prmaps.utxt").read()  # you should read in binary mode to get the BOM correctly
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
        return " ".join(wordLine)
    else:
        return name

def findScale(name):
    try:
        with open(LEVELSPATH + "/" + name + "/Heightdata.con") as f:
            lines = f.readlines()
            lineFound = False
            foundLine = ""
            for line in lines:
                if "heightmap.setScale" in line.replace("\n", ""):
                    lineFound = True
                    foundLine = line.replace("\n", "")
                    break
            splitLine = foundLine.split(" ")[1].split("/")
            scale = splitLine[0]
            lineFound = False
            foundLine = ""
            for line in lines:
                if "heightmap.setSize" in line.replace("\n", ""):
                    lineFound = True
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
        print e
        return -1

def generateJSON():
    print "Generating maps.json..."
    maplist = {}
    maps = get_immediate_subdirectories(LEVELSPATH)
    for map in maps:
        if map != '.svn':
            maplist[map] = {}
            maplist[map]['displayName'] = findDisplayName(map)
            maplist[map]['scale'] = findScale(map)
    with open("./input/maps.json", 'w') as f:
        f.write(json.dumps(maplist,indent=4))
    print "maps.json generated"

def main():
    generateJSON()
    generateMinimaps()

main()