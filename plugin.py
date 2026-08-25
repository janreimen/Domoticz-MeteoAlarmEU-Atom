# plugin for displaying weather warnigs
#
# Author: belze
#
"""
MeteoAlarmEU RSS Reader Plugin

Author: Belze(2018/2019/2020/2022), Ycahome(2017), JanReimen(2026)


Version:    1.0.0: Initial Version
            1.0.1: Minor bug fixes
            1.0.2: Bug Correction
            1.3.0: switched to from bs4 import BeautifulSoup by blz
            1.3.1: add option to show details and also use highest level for alarm level if multiple entries
            1.3.2: add option to show alarm icon from rss feed and switch language
            1.3.3: add option to use language from domoticz settings
            1.4.0: moved to extra class
            1.4.1: cleaned up a bit and added comments on functions
            1.4.2: bit more stability and better handling for wrong feed url
            1.5.0: new way to get rss feed
            1.6.0: switched over from RSS to ATOM Feeds
            1.6.1: fixed onStart/onHeartbeat crash when self.mt never got
                   initialized (UnboundLocalError in getMeteoLang, missing
                   pollinterval fallback); guarded onHeartbeat against
                   self.mt being None; fixed inverted error-backoff check;
                   fixed mktime(None) crash in getDayTitle when pubDate
                   is missing.
            1.6.2: added Health device (Unit 3) and Last Update device
                   (Unit 4); switched fixed 10-min error backoff to
                   exponential backoff (10/20/40/80, capped at 120 min);
                   added startup sanity check on the configured feed URL.
            1.6.3: meteo.py rewritten - the live feed no longer embeds an
                   HTML table/icons/per-language text (verified by
                   fetching it directly); parsing now reads the real CAP
                   fields (cap:event, cap:severity, cap:onset, cap:expires)
                   directly. Multi-day spans now split correctly across
                   Today/Tomorrow using real timestamps. Fixed a
                   pre-existing bug where German/Swedish detail-language
                   selection silently fell back to English; added
                   French/Spanish/Finnish translations. Dropped the bs4
                   and python-dateutil dependencies (no longer needed).
                   plugin.py itself is unchanged - Meteo's public
                   interface stayed the same.

"""
"""


<plugin key="MeteoAlarmEU Atom" name="Meteo Alarm EU RSS Reader Atom" author="belze,ycahome,janreimen" version="1.6.3" wikilink="" externallink="
http://www.domoticz.com/forum/viewtopic.php?f=65&t=19519">
     <description>
        <h2>Meteo Alarm EU RSS Reader eXtended</h2><br/>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>shows warnings for today and tomorrow</li>
            <li>using domoticz alarm level to signal the risk</li>
            <li>detail level can be chosen</li>
            <li>supports english, german, partly swedish</li>
            <li>use this langauge to grab matching warning from meteo</li>
            <li>icons from meteo can be embedded</li>
            <li>meteo publish date is shown in name</li>
            <li>if problems occur eg. missing libs - devices will show it</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>today - warnings for current day</li>
            <li>tomorrow - warnings for the next day</li>
        </ul>
        <h3>Hint</h3>
        First visit -><a href="https://feeds.meteoalarm.org/">
        Meteo</a> to choose your region and get rss-Feed link
    </description>

    <params>
        <param field="Mode1" label="RSSFeed" width="400px" required="true" default="https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-lux
embourg"/>
        <param field="Mode2" label="RSSCode" width="400px" required="true" default="202"/>
        <param field="Mode3" label="Update every x minutes" width="200px" required="true" default="300"/>
        <param field="Mode4" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="False" />
            </options>
        </param>
        <param field="Mode5" label="Details and Language for Status" width="200px"
        title="here you can choose if more details from rss should be shown and if so - which language to use">
            <options>
                <option label="NO_DETAIL" value="no_detail"  selected="selected"/>
                <option label="Details using domoticz lang" value="detail_dom_lang"/>
                <option label="Details in English" value="English"   />
                <option label="Details auf Deutsch" value="German"   />
                <option label="Details på Svenska" value="Swedish"   />
                <option label="Details in Spanish" value="Spanish"   />
                <option label="Details in French" value="French"   />
                <option label="Details in Finnish" value="Finnish"   />
            </options>
        </param>
        <param field="Mode6" label="Show Alarm Icons from RSS" width="200px">
            <options>
                <option label="NO_ICON" value="icon_no"  selected="selected"/>
                <option label="inline icon" value="icon_inline"   />
                <option label="inline icon with detail" value="icon_inline_detail"   />
            </options>
        </param>
    </params>
</plugin>
"""

import datetime as dt
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from os import path


from meteo import Meteo

# TODO
# - deeper look on from-until, sometimes until goes for a few days... in this case clock is not enough
# - langauge
#  - use langauge from dom Settings["Language"] - en,de,..
#  - if defined lang not found in rss -> english as fallback?
#  - clean up
# - more languages ..
# - icons as set?,
#  - 48png
#  - alarmtype must be integrated into alarm level, default is 0-4, eg: Alert48_22.png
#  - see www/app/UtilityController.js: img='<img src="images/Alert48_' + item.Level + '.png" height="48" width="48">';
#  - https://www.meteoalarm.eu/documents/rss/wflag-l4-t10.jpg
#  - https://www.meteoalarm.eu/theme/common/pictures/aw104.jpg


try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz

# sys.path
# sys.path.append('/usr/lib/python3/dist-packages')
# sys.path.append('/volume1/@appstore/py3k/usr/local/lib/python3.5/site-packages')
# sys.path.append('C:\\Program Files (x86)\\Python37-32\\Lib\\site-packages')

# fallback polling interval (minutes) used if Mode3 is missing/invalid
DEFAULT_POLL_MINUTES = 300

# exponential backoff steps (minutes) applied after every 10th consecutive
# error; index = (errorCounter // 10) - 1, clamped to the last entry
BACKOFF_STEPS_MINUTES = [10, 20, 40, 80, 120]

# used only for an early sanity-check warning in onStart(), not for
# validation/rejection - a non-matching URL still gets used as configured
EXPECTED_FEED_HOST = "feeds.meteoalarm.org"
EXPECTED_FEED_PATH_HINT = "atom"


class BasePlugin:

    def __init__(self):
        self.debug = False
        self.error = False
        self.errorCounter = 0
        self.nextpoll = datetime.now()
        self.detailNo = True
        self.detailLang = "english"
        self.iconNo = True

        self.iconType = ''
        self.langKey = 0  # 0 = english, 1 = german, 2 = ?

        self.rss = None
        self.mt = None
        self.pollinterval = DEFAULT_POLL_MINUTES * 60
        self.lastSuccessfulUpdate = None
        return

    def onStart(self):
        if Parameters["Mode4"] == 'Debug':
            self.debug = True
            Domoticz.Debugging(1)
            DumpConfigToLog()
        else:
            Domoticz.Debugging(0)

        Domoticz.Debug("onStart called")

        # check polling interval parameter
        # (fixed: previously, if int() raised, self.pollinterval was never
        # assigned since it only happened inside the try's `else` clause -
        # the very next Domoticz.Log() line would then throw
        # AttributeError: 'BasePlugin' object has no attribute 'pollinterval',
        # aborting onStart() before self.mt ever got created.)
        try:
            temp = int(Parameters["Mode3"])
        except (ValueError, TypeError):
            temp = DEFAULT_POLL_MINUTES
            Domoticz.Error("Invalid polling interval parameter '{}', falling back to {} minutes"
                            .format(Parameters.get("Mode3"), temp))

        if temp < 5:
            temp = 5  # minimum polling interval
            Domoticz.Error("Specified polling interval too short: changed to 5 minutes")
        elif temp > 1440:
            temp = 1440  # maximum polling interval is 1 day
            Domoticz.Error("Specified polling interval too long: changed to 1440 minutes (1 day)")
        self.pollinterval = temp * 60
        Domoticz.Log("Using polling interval of {} seconds".format(str(self.pollinterval)))

        self.rssUrl = Parameters["Mode1"]
        self.rssCode = Parameters["Mode2"]

        # sanity-check the feed URL early - doesn't block startup, just
        # surfaces a clear warning immediately instead of an obscure parse
        # error on the first heartbeat (e.g. if it's still set to an old
        # legacy-rss URL after the RSS->Atom migration)
        if EXPECTED_FEED_HOST not in self.rssUrl:
            Domoticz.Error("Configured RSSFeed URL '{}' does not look like a {} URL - check Mode1 in hardware settings"
                            .format(self.rssUrl, EXPECTED_FEED_HOST))
        elif EXPECTED_FEED_PATH_HINT not in self.rssUrl.lower():
            Domoticz.Error("Configured RSSFeed URL '{}' does not look like an Atom feed - "
                            "legacy RSS feeds were sunset; use a '...legacy-atom-<region>' URL"
                            .format(self.rssUrl))

        # (fixed: wrap Meteo() construction so any failure inside it -
        # e.g. an unmapped Domoticz language code - is caught, logged
        # clearly, and self.mt stays explicitly None instead of leaving
        # the attribute entirely unset.)
        self.mt = None
        try:
            self.mt = Meteo(self.rssUrl, rssCode=self.rssCode,
                            domLangSetting=Settings["Language"], detailSetting=Parameters["Mode5"],
                            iconSetting=Parameters["Mode6"], locationName=Parameters["Name"])
        except Exception as e:
            Domoticz.Error("Failed to initialize Meteo instance: {}".format(e))
            return

        if self.debug is True:
            self.mt.dumpMeteoConfig()  # (fixed: was missing () - never actually called)

        # Check if devices need to be created
        createDevices()

        # init with empty data
        updateDevice(1, 0, "No Data")
        updateDevice(2, 0, "No Data")
        updateDevice(3, 0, "OK", alwaysUpdate=True)
        updateDevice(4, 0, "never", alwaysUpdate=True)

    def onStop(self):
        Domoticz.Debug("onStop called")
        Domoticz.Debugging(0)

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug(
            "onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    def onHeartbeat(self):
        # (fixed: guard against onStart having failed before self.mt was
        # set - previously this crashed with
        # AttributeError: 'BasePlugin' object has no attribute 'mt'
        # on every single heartbeat once onStart failed early.)
        if self.mt is None:
            Domoticz.Error("Plugin not initialized (self.mt is None) - check onStart errors above, skipping heartbeat")
            return

        now = datetime.now()
        if now >= self.nextpoll:

            self.mt.readMeteoWarning()
            # check if error
            if(self.mt.hasError is True):
                Domoticz.Error("Error #{} on reading feed ".format(self.errorCounter))
                self.errorCounter += 1
                self.nextpoll = now
                txt = self.mt.errorMsg
                updateDevice(1, 4, txt, self.mt.getTodayTitle())
                updateDevice(2, 4, txt, self.mt.getTomorrowTitle())
                updateDevice(3, 1, "ERROR #{}: {}".format(self.errorCounter, txt))
                # (fixed in 1.6.1: was `if(self.errorCounter % 10):` which is
                # truthy for every count EXCEPT exact multiples of 10 - i.e.
                # it backed off on almost every error instead of only every
                # 10th one. Correct check needs `== 0`.)
                if(self.errorCounter % 10 == 0):
                    self.mt.reset()
                    backoffIndex = min((self.errorCounter // 10) - 1, len(BACKOFF_STEPS_MINUTES) - 1)
                    backoffMinutes = BACKOFF_STEPS_MINUTES[backoffIndex]
                    Domoticz.Error("got {} times an error, wait {} min before try again"
                                    .format(self.errorCounter, backoffMinutes))
                    self.nextpoll = now + timedelta(minutes=backoffMinutes)
            else:
                # no error, reset counter
                self.errorCounter = 0
                self.lastSuccessfulUpdate = now
                self.nextpoll = now + timedelta(seconds=self.pollinterval)
                updateDevice(3, 0, "OK")
                updateDevice(4, 0, "{:%Y-%m-%d %H:%M:%S}".format(self.lastSuccessfulUpdate), alwaysUpdate=True)
                if self.mt.needUpdate is True:
                    updateDevice(1, self.mt.todayLevel, self.mt.todayDetail, self.mt.getTodayTitle())
                    updateDevice(2, self.mt.tomorrowLevel, self.mt.tomorrowDetail, self.mt.getTomorrowTitle())
            Domoticz.Debug("----------------------------------------------------")


global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

#############################################################################
#                   common functions                                        #
#############################################################################


# Generic helper functions


def DumpConfigToLog():
    '''just dumps the configuration to log.
    '''
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return


def parseIntValue(s):
    """Parse an int and return None if no int is given
     Arguments:
        s {str} -- string of int value
    Returns:
        int -- the value in int or None
    """
    try:
        return int(s)
    except:
        return None

#
# Parse a float and return None if no float is given
#


def parseFloatValue(s):

    try:
        return float(s)
    except:
        return None


#############################################################################
#                       Device specific functions                           #
#############################################################################


def createDevices():
    '''
    this creates the device for today and tomorrow, if they are not in device-list
    '''

    # create the mandatory child devices if not yet exist
    if 1 not in Devices:
        Domoticz.Device(Name="Today", Unit=1, TypeName="Alert", Used=1).Create()
        Domoticz.Log("Devices[1] created.")
    if 2 not in Devices:
        Domoticz.Device(Name="Tomorrow", Unit=2, TypeName="Alert", Used=1).Create()
        Domoticz.Log("Devices[2] created.")
    # new in 1.6.2: health status device - lets you build a Domoticz
    # notification/automation off plugin health without parsing alert text
    if 3 not in Devices:
        Domoticz.Device(Name="Plugin Status", Unit=3, TypeName="Alert", Used=1).Create()
        Domoticz.Log("Devices[3] (Plugin Status) created.")
    # new in 1.6.2: last successful update timestamp - makes a silently
    # stuck feed visible in the Domoticz UI instead of only in logs
    if 4 not in Devices:
        Domoticz.Device(Name="Last Successful Update", Unit=4, TypeName="Text", Used=1).Create()
        Domoticz.Log("Devices[4] (Last Successful Update) created.")


#
def updateDevice(Unit, highestLevel, alarmData, name='', alwaysUpdate=False):
    '''update a device - means today or tomorrow, with given data.
    If there are changes and the device exists.
    Arguments:
        Unit {int} -- index of device, 1 = today, 2 = tomorrow
        highestLevel {[type]} -- the maximum warning level for that day, it is used to set the domoticz alarm level
        alarmData {[str]} -- data to show in that device, aka text

    Optional Arguments:
        name {str} -- optional: to set the name of that device, eg. mor info about  (default: {''})
        alwaysUpdate {bool} -- optional: to ignore current status/needs update (default: {False})
    '''

    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if Unit in Devices:
        if (alarmData != Devices[Unit].sValue) or (int(highestLevel) != Devices[Unit].nValue or alwaysUpdate is True):
            if(len(name) <= 0):
                Devices[Unit].Update(int(highestLevel), str(alarmData))
            else:
                Devices[Unit].Update(int(highestLevel), str(alarmData), Name=name)
            Domoticz.Log("BLZ: Awareness Updated to: {} value: {}".format(alarmData, highestLevel))
        else:
            Domoticz.Log("BLZ: Awareness Remains Unchanged")
    else:
        Domoticz.Error("Devices[{}] is unknown. So we cannot update it.".format(Unit))
