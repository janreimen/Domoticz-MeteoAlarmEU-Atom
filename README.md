# MeteoAlarmEU-Atom
 [![Plugin version](https://img.shields.io/badge/version-1.7.0-red.svg)]()

## !New version - that supports meteoalarm.org Atom feeds!

Show warnings from [meteoalarm.org](http://www.meteoalarm.org/) inside your Domoticz.

![settings](https://github.com/belzetrigger/domoticz-MeteoAlarmEU/raw/master/resources/unit_en_ml_warnings.PNG)

## Summary
This is a virtual hardware plugin that adds information about extreme weather from [meteoalarm.org](http://www.meteoalarm.org/) to your [Domoticz](https://www.domoticz.com/) interface. It generates:
- **Today** / **Tomorrow** - the alert sensors for your primary region
- **Plugin Status** - reflects whether the last feed fetch succeeded, so you can wire a Domoticz notification off plugin health without parsing alert text
- **Last Successful Update** - timestamp of the last clean fetch, so a silently stuck feed is visible in the UI instead of only in logs
- as of 1.7.0, an additional **Today (\<code\>)** / **Tomorrow (\<code\>)** pair for each extra region you configure (see Settings below)

As this is a european meteorological service it only works in Europe. And you also shoud check [meteoalarm.org](meteoalarm.org) if your country is participating.

This plugin is open source.

> **Note:** meteoalarm.org sunset its legacy RSS feeds. This fork switched to the Atom feed format (see Changelog 1.6.0) and is maintained here as a separate repo from the original [belzetrigger/domoticz-MeteoAlarmEU](https://github.com/belzetrigger/domoticz-MeteoAlarmEU).

## Installation and Setup
- a running Domoticz, tested with 4.10038 and 2026.1
- Python 3.13
- install needed python moduls:
  - feedparser
  - (as of 1.6.3, `beautifulsoup4` and `python-dateutil` are no longer required - the parser now reads the feed's structured CAP fields directly instead of scraping an embedded HTML table, and uses the standard library for date parsing)
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
-  RSSCode (primary region)
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
-  Additional Region Codes (new in 1.7.0): optional, comma-separated (eg `DE201,DE203`) - each gets its own Today/Tomorrow device pair. Must be regions within the **same** feed/country as RSSFeed above (one fetch is shared across all configured regions each poll); for a different country, add the hardware a second time instead.

-  Update:  time to wait till next poll (minutes). If this value is missing or invalid, the plugin now falls back to the 300-minute default instead of failing to start.
-  Debug: if True, the log will be hold a lot more output - including a preview of the raw feed response if a fetch/parse ever fails, and any feedparser warnings about a malformed feed.
-  Details and Language:
    -  NO_Detail
    -  Details Domoticz Languag: - just grab the language from domoticz and use it
    -  Details in english - ignore domoticz settings, just search for english details
    -  Details auf deutsch - ignore domoticz settings, just search for german details
    -  Details pa svenska - ignore domoticz settings, just search for swedish details
-  Show Alarm Icons: as of 1.7.0, this controls the plugin's own bundled severity+type icon set (meteoalarm's own colour scale x 12 warning categories), since the feed itself no longer provides icons.
    -  NO_ICON: use Domoticz's default Alert icon
    -  inline icon / inline icon with detail: use the bundled per-type icon matching the day's worst warning

## Bugs and ToDos
1. **Icon zip packaging is unverified against a live Domoticz instance.** `meteoalarm_icons.zip` (bundled severity+type icons) was built against Domoticz's documented custom-icon conventions (see [wiki: Developing a Python plugin#Images](http://www.domoticz.com/wiki/Developing_a_Python_plugin#Images)) and passed a simulated test harness, but real-world Domoticz behavior for plugin-bundled icons on Alert-type devices has conflicting documentation in the Domoticz community itself. If icons don't appear after upgrading, the plugin still works normally (falls back to the default Alert icon) - please report back what you see so this can be fixed for real.
2. Event-type detection (thunderstorm/rain/wind/etc.) is done via keyword matching against the entry title and `cap:event` text. Only Thunderstorm, Rain, Coastal Event, and Forest-fire have been checked against real live/historical feed data; Wind, Snow/Ice, Fog, High/Low Temp, Avalanches, and Flood are implemented from MeteoAlarm's documented category list but not yet confirmed against a real warning.
3. Multi-region support (1.7.0) only covers multiple regions within the *same* country/feed URL, sharing one fetch per heartbeat. Monitoring regions in different countries still needs a separate hardware instance per country.
4. Think about how to use warning in the domoticz systems. For example do something with the blinds on strong wind, or stop/delay watering the garden if ..
5. More Domoticz language codes could be mapped beyond the current en/de/sv/fr/es/fi - an unmapped language now falls back gracefully to English rather than crashing.
6. `cap:certainty` and `cap:message_type` (Alert vs Update) are fetched but not yet surfaced anywhere - only `cap:urgency` (upcoming/ending) is currently shown.

## How it Works in details
As of 1.6.3, the feed is parsed directly from its structured CAP fields rather than scraping an embedded HTML table (the old format is no longer served - verified by fetching the live feed directly). Each configured region (RSSCode plus any Additional Region Codes) gets its own `Meteo` instance, but as of 1.7.0 all regions share a **single fetch per heartbeat** of the feed rather than each region re-fetching it. For each region's matching entries:
- the region code is matched against the entry's `geocode=EMMA_ID:...` link (falling back to feedparser's flattened `cap:geocode` value) - matched exactly, not by substring
- only `cap:status: Actual` entries count - Test/Exercise/Draft/System messages (part of the CAP spec, used for system testing) are skipped
- the warning type (thunderstorm/rain/wind/etc.) and colour level (green/yellow/orange/red) are read from the entry title and `cap:severity`, and translated via the plugin's own built-in language table (en/de/sv/fr/es/fi) - this is no longer dependent on the feed publishing multiple languages itself, since it currently only publishes in English
- `cap:onset`/`cap:expires` (real timestamps) decide whether a warning belongs to Today, Tomorrow, or both - a warning spanning multiple days now correctly appears in both, with the non-today end shown as a date + day-offset (eg `+1d`)
- `cap:urgency` of `Future`/`Past` is shown as `[upcoming]`/`[ending]` in verbose detail mode
- the worst level across all matching warnings for that day picks the Domoticz alarm sensor level and (if icons are enabled) the matching bundled icon
- whether devices actually need updating is decided by comparing the rendered text/level before and after each poll, not by a date proxy

The feed itself is fetched with a 15s timeout so a hung connection can't block the whole Domoticz heartbeat cycle, and the Plugin Status / Last Successful Update devices reflect the outcome after every poll.

## Developing
Based on https://github.com/ffes/domoticz-buienradar/ there are
 -  `fakeDomoticz.py` - simulates enough of the Domoticz plugin framework (Devices, Images, Log/Debug/Error) to run `plugin.py`'s `onStart()`/`onHeartbeat()` outside Domoticz
 -  `testMeteo.py` - a real `unittest` suite (`python3 testMeteo.py`) covering cap:status filtering, the needUpdate fingerprint, multi-day span splitting, urgency tagging, the language-mapping fixes, icon key lookup, and exact-match region code extraction. Test data uses dates relative to when the tests run, not hardcoded dates, so they don't go stale.

## ChangeLog
1.7.0: fixed `DOM_LANG_TO_METEO['se']` -> `'sv'` (Domoticz's real Swedish language code - `'se'` never matched anything, silently equivalent to not mapping Swedish at all). Added `cap:status` filtering - Test/Exercise/Draft/System entries (part of the CAP spec, not real warnings) are now excluded, only `Actual` alerts show. `needUpdate` is now a real before/after fingerprint of the rendered text instead of a `pubDate`-based proxy. `cap:urgency` of `Future`/`Past` now shows as `[upcoming]`/`[ending]` in verbose mode. Added multi-region support: an "Additional Region Codes" field accepts comma-separated extra region codes (same feed/country), each getting its own Today/Tomorrow device pair, all sharing one feed fetch per heartbeat instead of one fetch per region. Added a bundled severity+type icon set (12 warning categories x meteoalarm's 4-colour scale) replacing the icons the feed itself no longer provides - **this specific piece is built against documented Domoticz conventions but not verified against a live instance**; the plugin functions normally with the default Alert icon if icon loading fails for any reason. Added a real `testMeteo.py` test suite (15 tests, run via `python3 testMeteo.py`) and a fuller `fakeDomoticz.py` that simulates device/image creation, exercising `onStart()`/`onHeartbeat()` end-to-end including the multi-region device allocation.
1.6.3: meteo.py's parser rewritten against the real, currently-live CAP-Atom feed structure (verified by fetching it directly) - the old code assumed an HTML table with icons and per-language text embedded in each entry's description, which the feed no longer provides and which would throw on every matching entry against real data. Parsing now reads cap:event/cap:severity/cap:onset/cap:expires directly. Multi-day spans now correctly split a warning across Today and Tomorrow using real timestamps instead of dropping it once "today" no longer applies. Fixed a pre-existing bug where selecting German or Swedish for detail language silently fell back to English (getLangIndex was checking for the Swedish/German native-language words instead of the English names actually used). Added French/Spanish/Finnish translations to the built-in warning-type table. The "Show Alarm Icon" setting no longer has any visual effect, since the feed provides no per-warning icon images at all anymore. Dropped the beautifulsoup4 and python-dateutil dependencies - only feedparser is required now.
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
