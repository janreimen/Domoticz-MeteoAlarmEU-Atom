# MeteoAlarmEU-Atom
 [![Plugin version](https://img.shields.io/badge/version-1.6.2-red.svg)]()

## !New version - that supports meteoalarm.org Atom feeds!

Show warnings from [meteoalarm.org](http://www.meteoalarm.org/) inside your Domoticz.

![settings](https://github.com/belzetrigger/domoticz-MeteoAlarmEU/raw/master/resources/unit_en_ml_warnings.PNG)

## Summary
This is a virtual hardware plugin that adds information about extreme weather from [meteoalarm.org](http://www.meteoalarm.org/) to your [Domoticz](https://www.domoticz.com/) interface. It generates four devices:
- **Today** / **Tomorrow** - the alert sensors showing latest warnings
- **Plugin Status** - reflects whether the last feed fetch succeeded, so you can wire a Domoticz notification off plugin health without parsing alert text
- **Last Successful Update** - timestamp of the last clean fetch, so a silently stuck feed is visible in the UI instead of only in logs

As this is a european meteorological service it only works in Europe. And you also shoud check [meteoalarm.org](meteoalarm.org) if your country is participating.

This plugin is open source.

> **Note:** meteoalarm.org sunset its legacy RSS feeds. This fork switched to the Atom feed format (see Changelog 1.6.0) and is maintained here as a separate repo from the original [belzetrigger/domoticz-MeteoAlarmEU](https://github.com/belzetrigger/domoticz-MeteoAlarmEU).

## Installation and Setup
- a running Domoticz, tested with 4.10038 and 2026.1
- Python 3.13
- install needed python moduls:
  - beautifullsoup bs4
  - feedparser
  - python-dateutil
  - you can use `sudo pip3 install -r requirements.txt`
- clone project
    - go to `domoticz/plugins` directory
    - clone the project
        ```bash
        cd domoticz/plugins
        git clone https://github.com/janreimen/Domoticz-MeteoAlarmEU-RSS-Atom.git
        ```
- or just download, unzip and copy to `domoticz/plugins`
- no need on Raspbian for sys path adaption if using sudo for pip3
- some extra work for Windows or Synology, make sure downloaded modules are in path eg. site-packages python paths or change in plugin.py / fritzHelper.py path
- restart Domoticz service
- Now go to **Setup**, **Hardware** in your Domoticz interface. There add
**MeteoAlarmEU Atom**.
### Settings
![settings](https://github.com/belzetrigger/domoticz-MeteoAlarmEU/raw/master/resources/settings.PNG)

- RSSFeed:
    -  go to [meteoalarm.org](https://feeds.meteoalarm.org/)
    -  select your **legacy-atom** feed for your country eg: `https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-germany` for Germany (legacy RSS feeds are sunset - use the atom URL)
    - add this link to RSSFeed
-  RSSCode
    - get the region-code
    -  if you know the old code all is fine. It was name of the old rss  like .../FI001.rss goes FI001
    -  otherwise
    -  go to https://meteoalarm.org/en/page/re-users
    -  check for downloading 'geocodes json' -> download the file
        -  search for our town / region check eg Berlin
        -  there you will find for select your region:
              ```
              {"code":"DE202","country":"DE","name":"Stadt Berlin","type":"EMMA_ID"}
              ```
        - copy the code, the numbers should do it

-  Update:  time to wait till next poll (minutes). If this value is missing or invalid, the plugin now falls back to the 300-minute default instead of failing to start.
-  Debug: if True, the log will be hold a lot more output - including a preview of the raw feed response if a fetch/parse ever fails, and any feedparser warnings about a malformed feed.
-  Details and Language:
    -  NO_Detail
    -  Details Domoticz Languag: - just grab the language from domoticz and use it
    -  Details in english - ignore domoticz settings, just search for english details
    -  Details auf deutsch - ignore domoticz settings, just search for german details
    -  Details pa svenska - ignore domoticz settings, just search for swedish details
-  Show Alarm Icon:
    -  NO_ICON: We do not show the warning image from meteo rss feed
    -  inline icon: we show the little alarm icon from meteo
    -  inline icon with detail: we show the icon and also add the warning text as tool tip

## Bugs and ToDos
1. Inline images reference to meteo for example https://www.meteoalarm.eu/documents/rss/wflag-l2-t2.jpg  This means if client does not have access, it will be blank.
2. Think about how to use warning in the domoticz systems. For example do something with the blinds on strong wind, or stop/delay watering the garden if ..
3. More Domoticz language codes could be mapped to Meteo languages beyond the current en/de/se/fr/es/fi - an unmapped language now falls back gracefully to English rather than crashing, but proper native-language support for more languages is still open.
4. Severity+type combined alert icons (matching Domoticz's own icon set) instead of relying solely on the inline image from the feed.

## How it Works in details
Takes the feed from meteo and scans it for:
- matching code
- today / tomorrow: to know which device must be updated
- icons:
    - to get the type of warning and alarm level
    - to use the same url on the device text to show image
- keep the worst alarm level per day and use it for Domoticz alarm sensor
- updateDate aka 'publish Date' of feed: to know if there is a change, and so devices should be updated too
- language in warning message. because content is like [language]: blabla
- for warnings spanning more than a day, the from/until times now show the date and a day-offset (eg `+1d`) instead of silently dropping the date once it no longer matches "today"/"tomorrow"

Collect all those data per day and puts it on domoticz alarm devices. The feed itself is now fetched with a 15s timeout so a hung connection can't block the whole Domoticz heartbeat cycle, and the Plugin Status / Last Successful Update devices reflect the outcome after every poll.

## Developing
Based on https://github.com/ffes/domoticz-buienradar/ there are
 -  `fakeDomoticz.py` - used to run it outside of Domoticz
 -  `testMeteo.py` it's the entry point for tests

## ChangeLog
1.6.2: added Plugin Status and Last Successful Update devices; explicit 15s timeout on the feed fetch instead of an unbounded one; exponential error backoff (10/20/40/80, capped at 120 min) instead of a flat 10-minute retry; startup sanity check on the configured feed URL; from/until times for multi-day warnings now show date + day-offset instead of dropping the date; feedparser "bozo" (malformed feed) warnings and a raw-feed preview on parse failure are now logged in Debug mode.
1.6.1: fixed onStart/onHeartbeat crash when self.mt never got initialized (UnboundLocalError in getMeteoLang on an unmapped Domoticz language, and a missing pollinterval fallback on an invalid Update setting); guarded onHeartbeat against self.mt being None; fixed inverted error-backoff check; fixed a crash showing the device title when a feed poll returned zero matching entries.
1.6.0: switched over from RSS to ATOM Feeds
1.5.0: reworked a bit to work now with the new 'legacy-rss-feed'
1.4.2: bit more stability and better handling for wrong feed url
1.4.1: cleaned up a bit and added comments on functions
1.4.0: moved to extra class
1.3.3: add option to use language from domoticz settings
1.3.2: add option to show alarm icon from rss feed and switch language
1.3.1: add option to show details and also use highest level for alarm level if multiple entries
1.3.0: switched to from bs4 import BeautifulSoup by blz
1.0.2: Bug Correction
1.0.1: Minor bug fixes
1.0.0: Initial Version
