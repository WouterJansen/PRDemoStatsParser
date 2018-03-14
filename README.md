# PRDemoStatsParser
Script for generating data(statistics, heatmaps,...) from PRDemo(PR Tracker) files.
Will create a _data_ folder with all generated content. This can then be used with the webservice to display it. (https://github.com/WouterJansen/prbf2stats).

## Requirements
* Python 2.7.
* Needs python packages **numpy**, **requests** and **beautifulsoup4**.

## Optional
* Supports a folder _input_ with all minimaps as jpg's of size 512x512 with their name as the mapname (to display heatmaps on). 
* A ```maps.json``` in the _input_ folder with information on the display name and the scale of the map(1,2,4 or 8). Without the scale defined there will be no heatmap data generated. Format:
```javascript
{
  "albasrah_2": {
    "displayName": "Al Basrah",
    "scale": 2
  },
  "iron_thunder": {
    "displayName": "Operation Thunder - BETA",
    "scale": 4
  }
}
```
* You can use the ```generateInput.py```(requires **PIL/Pillow**) script to generate the ```maps.json``` and minimap images automatically. It requires one argument, your MODPATH where it can find a fully extracted PR. (ex. ```python generateInput.py "C:\Program Files (x86)\Project Reality\Project Reality BF2\mods\pr_repo"```)
* A ```servers.json``` in the _input_ folder with information on which servers and their corresponding URLs to look for PRDemo download links. Format:
```javascript
{
    "servers": [
        {
            "demos": [],
            "links": [ "www.community1.com/tracker/server1/", "www.community1.com/tracker/server2/" ], 
            "name": "servername1"
        },
	{
	    "demos": [],
            "links": [ "www.community2.com/tracker/" ], 
            "name": "servername2"
        }
    ]
}
```
## How To
* Place PRDemo files in a _demos_ folder or create a ```servers.json``` in the _input_ folder to automatically download them(see Optional).
* run ```PRDemoParser.py```.

## Notes 
* After parsing the _demos_ folder will be automatically cleared to save space.
* For usage in Project Reality: Battlefield 2. http://www.realitymod.com
