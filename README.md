# PRDemoStatsParser
Script for generating map stats from PRDemo(PR Tracker) files.
Will create the statistics per map in the ```data``` folder.
Data can then be used with the webservice (https://github.com/WouterJansen/prbf2stats).

## Requirements
* Python 2.7.
* Needs python packages **requests** and **beautifulsoup4**.
* A ```servers.json``` next to the script with information on which servers and their corresponding URLs to look for RPDemo download links. Format:
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
## Optional
* Supports a folder ```input``` with all minimaps as jpg's of size 512x512 with their name as the mapname. And a ```maps.json``` next to the images with information on the display name and the scale of the map(1,2,4 or 8):
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
## Important
* After parsing the demos will be automatically removed!

For usage in Project Reality: Battlefield 2. http://www.realitymod.com
