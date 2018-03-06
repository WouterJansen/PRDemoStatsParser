# PRDemoStatsParser
Script for generating map stats from PRDemo(PR Tracker) files.
Will create the statistics per map in the ```maps``` folder.
Data can then be used with the webservice (https://github.com/WouterJansen/prbf2stats).

## Requirements
* Python 2.7.
* Needs python packages **requests** and **beautifulsoup4**.
* A ```servers.json``` next to the script with information on which servers and their corresponding URLs to look for RPDemo download links. Format:
```javascript
{
    "servers": [
        {
            "links": [ "www.community1.com/tracker/server1/", "www.community1.com/tracker/server2/" ], 
            "name": "servername1"
        },
		{
            "links": [ "www.community2.com/tracker/" ], 
            "name": "severname 2"
        }
    ]
}
```
## Optional
* Supports a localization file ```maps.json``` next to the script to allow for a different displayed name for the map.
Format:
```javascript
{
    "assault_on_grozny": "Assault on Grozny",
	"iron_thunder": "Operation Thunder"
}
```
## Important
* After parsing the demos will be automatically removed!

For usage in Project Reality: Battlefield 2. http://www.realitymod.com
