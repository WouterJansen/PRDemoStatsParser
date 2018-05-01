# PRDemoStatsParser
Script for generating statistical data from PRDemo(PR Tracker) files from The Battlefield 2: Project reality modification. This data can then be used with the webservice to display it. (https://github.com/WouterJansen/prbf2stats).

## Requirements
* Python 2.7.
* Needs python packages **pyheatmap**,**PIL**, **numpy**, **requests** and **beautifulsoup4**.

## Configuration (optional)
* Supports a folder _input_ with all minimaps as jpg's of size 512x512 with their name as the mapname (to display heatmaps on). (These can be generated automatically by ```generateInput.py```, see below)
* A ```maps.json``` in the _input_ folder with information on the display name and the scale of the map(1,2,4 or 8). Without the scale defined there will be no heatmap data generated. (This can be generated automatically by ```generateInput.py```, see below) Format:
```javascript
{
  "albasrah_2": {
    "displayName": "Al Basrah (2km)",
    "scale": 2
  },
  "iron_thunder": {
    "displayName": "Operation Thunder - BETA (4km)",
    "scale": 4
  }
}
```
* A ```config.json``` in the _input_ folder with (see format below):
    * The path to your pr_repo (used by ```generateInput.py```, see below).
    * The path to your web-folder where the data is used. Setting this allows for automatic copying of the data folder to this path. 
    * information on which servers and their corresponding URLs to look for PRDemo download links. It can also be to a JSON where it uses a crawler to find the download links. See example link in code below.
```javascript
{
    "prpath": "D:/Project Reality/Project Reality BF2/mods/pr_repo",
    "webpath": "C:/prbf2stats/dist",
    "servers": [
        {
            "demos": [],
            "links": [ "https://projects.uturista.pt/trackers/tracker.json" ],
            "name": "Crawler Servers"
        },
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
* You can use the ```generateInput.py``` script (requires **PIL/Pillow**)  to generate the ```maps.json``` and minimap images automatically. Requires the path to the fully extracted pr_repo set in ```config.json``` (see above).
## How To
* (Optional: run ```generateInput.py``` to create the input files)
* Place PRDemo files in a _demos_ folder or create a ```config.json``` in the _input_ folder to automatically download them (see Optional).
* run ```PRDemoParser.py```.

## Notes 
* After parsing the _demos_ folder will be automatically emptied to save disk space.
* For usage in Project Reality: Battlefield 2. http://www.realitymod.com
