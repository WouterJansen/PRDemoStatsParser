# PRDemoStatsParser
Script for generating data(statistics, heatmaps,...) from PRDemo(PR Tracker) files.
Will create a ```data``` folder with all generated content. This can then be used with the webservice to display it. (https://github.com/WouterJansen/prbf2stats).

## Requirements
* Python 2.7.
* Needs python packages **numpy**, **requests** and **beautifulsoup4**.

## Optional
* Supports a folder ```input``` with all minimaps as jpg's of size 512x512 with their name as the mapname (to display heatmaps with). 
* A ```maps.json``` in the ```input``` folder with information on the display name and the scale of the map(1,2,4 or 8). Without the scale defined there will be no heatmap data generated. Format:
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
* A ```servers.json``` in the ```input``` folder with information on which servers and their corresponding URLs to look for RPDemo download links. Format:
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
## Notes 
* After parsing the ```demos``` will be automatically cleared to save space.
* For usage in Project Reality: Battlefield 2. http://www.realitymod.com
