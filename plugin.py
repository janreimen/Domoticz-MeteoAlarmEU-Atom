# plugin for displaying weather warnigs
#
# Author:janreimen
#
"""
MeteoAlarmEU RSS Reader Plugin

Author: Belze(2018/2019/2020/2022), Ycahome(2017), JanReimen(2026)



Version:    1.0.0-1.5.0: original belze/ycahome plugin - initial version
                  through bug fixes, BeautifulSoup-based RSS parsing,
                  detail/language/icon options, and a class-based rewrite.

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

            1.7.0: fixed DOM_LANG_TO_METEO['se'] -> 'sv' (Domoticz's real
                  Swedish code - 'se' never matched anything). Added
                  cap:status filtering (Test/Exercise/Draft/System
                  entries are now skipped - only Actual alerts show).
                  needUpdate is now a real before/after content
                  fingerprint instead of a pubDate-based proxy.
                  cap:urgency is now shown for not-yet-active/ending
                  warnings ([upcoming]/[ending]). Added multi-region
                  support: the "Address" field (previously unused by
                  this plugin) now accepts additional comma-separated
                  region codes, each getting its own Today/Tomorrow
                  device pair, sharing a single feed fetch per
                  heartbeat rather than fetching once per region.
                  Added a bundled severity+type icon set (meteoalarm's
                  own 4-colour scale x 12 warning categories) loaded
                  from meteoalarm_icons.zip, replacing the feed-sourced
                  icons that no longer exist - NOTE: this specific piece
                  is built against documented conventions but has not
                  been verified against a live Domoticz instance; if
                  icons don't appear, the plugin still works normally,
                  it just falls back to the default Alert icon.

            1.7.1: fixed getDayIconKey() ignoring self.iconNo (NO_ICON
                  setting had no effect as long as the icon zip loaded).
                  Added Luxembourgish as a 7th detail-language option.
                  Removed dead code found during cleanup (unused
                  imports, unused Meteo/BasePlugin attributes, unused
                  helper functions). See CHANGELOG.md for full detail
                  and the reasoning behind each change.

                  Fixed multi-region device naming: the configured
                  region code is now included in the stable Domoticz
                  Today/Tomorrow device name for every configured region,
                  including the primary region. Existing devices are
                  automatically renamed on startup. Feed-generated day
                  titles no longer overwrite the region-qualified
                  device names.
                  See CHANGELOG.md for full detail and the reasoning
                  behind this change.

<plugin key="MeteoAlarmEU-Atom" name="Meteo Alarm EU RSS Reader Atom" author="belze,ycahome,janreimen" version="1.7.1" wikilink="" externallink="https://www.github.com/janreimen/Domoticz-MeteoAlarmEU-Atom.git">
    <description>
        <h2>Meteo Alarm EU RSS Reader eXtended</h2><br/>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>shows warnings for today and tomorrow, for one or more regions</li>
            <li>using domoticz alarm level to signal the risk</li>
            <li>detail level can be chosen</li>
            <li>supports english, german, swedish, french, spanish, finnish, luxembourgish</li>
            <li>meteo publish date is shown in device value</li>
            <li>if problems occur eg. missing libs - devices will show it</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>today / tomorrow - warnings for each configured region, with the region code in the device name</li>
            <li>Plugin Status / Last Successful Update - feed fetch health</li>
            <li>one Today/Tomorrow pair per configured region</li>
        </ul>
        <h3>Hint</h3>
        First visit -><a href="https://feeds.meteoalarm.org/">
        Meteo</a> to choose your region and get rss-Feed link
    </description>
    <params>
        <param field="Mode1" label="RSSFeed" width="400px" required="true" default="https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-luxembourg"/>
        <param field="Mode2" label="RSSCode(s) (comma-separated regions)" width="400px" required="true" default="LU002, LU001"/>
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
                <option label="NO_DETAIL" value="no_detail" />
                <option label="Details using domoticz lang" value="detail_dom_lang"/>
                <option label="Details in English" value="English"   />
                <option label="Details auf Deutsch" value="German"   />
                <option label="Details på Svenska" value="Swedish"   />
                <option label="Details in Spanish" value="Spanish"   />
                <option label="Details in French" value="French"   />
                <option label="Details in Finnish" value="Finnish"   />
                <option label="Detailer op Lëtzebuergesch" value="Luxembourgish"  default="selected" />
            </options>
        </param>
        <param field="Mode6" label="Show Alarm Icons" width="200px"
        title="as of 1.7.0 this controls the plugin's own bundled severity+type icon set, since the feed itself no longer provides icons">
            <options>
                <option label="NO_ICON" value="icon_no"  selected="selected"/>
                <option label="inline icon" value="icon_inline"   />
                <option label="inline icon with detail" value="icon_inline_detail"   />
            </options>
        </param>
    </params>
</plugin>
"""

import os

from datetime import datetime, timedelta

import meteo
from meteo import Meteo

# KNOWN ISSUE - unverified: icon filenames/packaging format used by
# meteoalarm_icons.zip is built against documented Domoticz plugin-icon
# conventions but has not been confirmed against a live Domoticz instance.
# If icons don't appear, the plugin still works normally (falls back to
# the default Alert icon) - see README "Bugs and ToDos".


try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz

# If running on Windows or Synology and downloaded modules aren't found,
# add the relevant site-packages path here, e.g.:
# import sys; sys.path.append('/path/to/site-packages')

# fallback polling interval (minutes) used if Mode3 is missing/invalid
DEFAULT_POLL_MINUTES = 300

# exponential backoff steps (minutes) applied after every 10th consecutive
# error; index = (errorCounter // 10) - 1, clamped to the last entry
BACKOFF_STEPS_MINUTES = [10, 20, 40, 80, 120]

# used only for an early sanity-check warning in onStart(), not for
# validation/rejection - a non-matching URL still gets used as configured
EXPECTED_FEED_HOST = "feeds.meteoalarm.org"

EXPECTED_FEED_PATH_HINT = "atom"

# filename of the bundled custom icon zip, expected alongside plugin.py
ICON_ZIP_FILENAME = "meteoalarm_icons.zip"

# one representative image name used to check whether icons are already
# loaded, to avoid recreating them on every onStart()
ICON_PROBE_NAME = "MeteoAlarmEUAtomWindL1"


class BasePlugin:

    def __init__(self):
        self.debug = False
        self.errorCounter = 0
        self.nextpoll = datetime.now()
        self.meteoList = []  # list of Meteo instances, one per configured region
        self.rssUrl = None
        self.pollinterval = DEFAULT_POLL_MINUTES * 60
        self.lastSuccessfulUpdate = None
        self.iconsLoaded = False
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
        # (fixed in 1.6.1: previously, if int() raised, self.pollinterval was
        # never assigned since it only happened inside the try's `else`
        # clause - the very next Domoticz.Log() line would then throw
        # AttributeError, aborting onStart() before anything got initialized.)

        try:
            temp = int(Parameters["Mode3"])

        except (ValueError, TypeError):
            temp = DEFAULT_POLL_MINUTES
            Domoticz.Error(
                "Invalid polling interval parameter '{}', falling back to {} minutes"
                .format(Parameters.get("Mode3"), temp)
            )

        if temp < 5:
            temp = 5
            Domoticz.Error(
                "Specified polling interval too short: changed to 5 minutes"
            )

        elif temp > 1440:
            temp = 1440
            Domoticz.Error(
                "Specified polling interval too long: changed to 1440 minutes (1 day)"
            )

        self.pollinterval = temp * 60

        Domoticz.Log(
            "Using polling interval of {} seconds".format(
                str(self.pollinterval)
            )
        )

        self.rssUrl = Parameters["Mode1"]

        primaryCode = Parameters["Mode2"]

        # sanity-check the feed URL early - doesn't block startup, just
        # surfaces a clear warning immediately instead of an obscure parse
        # error on the first heartbeat

        if EXPECTED_FEED_HOST not in self.rssUrl:

            Domoticz.Error(
                "Configured RSSFeed URL '{}' does not look like a {} URL - check Mode1 in hardware settings"
                .format(
                    self.rssUrl,
                    EXPECTED_FEED_HOST
                )
            )

        elif EXPECTED_FEED_PATH_HINT not in self.rssUrl.lower():

            Domoticz.Error(
                "Configured RSSFeed URL '{}' does not look like an Atom feed - "
                "legacy RSS feeds were sunset; use a '...legacy-atom-<region>' URL"
                .format(self.rssUrl)
            )

        # additional region codes, comma-separated, sharing the same feed
        # URL - the primary Mode2 code is always index 0 and keeps the
        # original Unit 1/2 devices for backward compatibility

        additionalCodes = [
            c.strip()
            for c in Parameters.get("Mode2", "").split(",")
            if c.strip()
        ]

        allCodes = additionalCodes

        if additionalCodes:

            Domoticz.Log(
                "Monitoring {} regions: {}".format(
                    len(allCodes),
                    ", ".join(allCodes)
                )
            )

        self.meteoList = []

        for code in allCodes:

            try:

                mt = Meteo(
                    self.rssUrl,
                    rssCode=code,
                    domLangSetting=Settings["Language"],
                    detailSetting=Parameters["Mode5"],
                    iconSetting=Parameters["Mode6"],
                    locationName=Parameters["Name"]
                )

                self.meteoList.append(mt)

            except Exception as e:

                Domoticz.Error(
                    "Failed to initialize Meteo instance for region '{}': {}".format(
                        code,
                        e
                    )
                )

        if not self.meteoList:

            Domoticz.Error(
                "No Meteo instances could be initialized - plugin will not function until fixed"
            )

            return

        if self.debug is True:
            self.meteoList[0].dumpMeteoConfig()

        # load the bundled severity+type icon set. This is never allowed
        # to prevent the plugin from working - any failure here just
        # means devices fall back to the default Alert icon.

        self._loadIcons()

        createDevices(len(self.meteoList))

        # init with empty data
        #
        # Region-qualified names are explicitly supplied here and
        # alwaysUpdate=True ensures existing devices from earlier versions
        # are renamed even when their state/value has not changed.

        for i in range(len(self.meteoList)):

            todayUnit, tomorrowUnit = unitsForRegion(i)

            updateDevice(
                todayUnit,
                0,
                "No Data",
                name=deviceNameForRegion(i, tomorrow=False),
                alwaysUpdate=True
            )

            updateDevice(
                tomorrowUnit,
                0,
                "No Data",
                name=deviceNameForRegion(i, tomorrow=True),
                alwaysUpdate=True
            )

        updateDevice(
            3,
            0,
            "OK",
            alwaysUpdate=True
        )

        updateDevice(
            4,
            0,
            "never",
            alwaysUpdate=True
        )

    def _loadIcons(self):

        try:

            zipPath = os.path.join(
                Parameters.get("HomeFolder", ""),
                ICON_ZIP_FILENAME
            )

            if not os.path.exists(zipPath):

                Domoticz.Debug(
                    "Icon zip not found at {} - devices will use the default Alert icon."
                    .format(zipPath)
                )

                self.iconsLoaded = False

                return

            if ICON_PROBE_NAME not in Images:

                Domoticz.Image(
                    Filename=ICON_ZIP_FILENAME
                ).Create()

                Domoticz.Log(
                    "Custom severity/type icon set loaded from {}."
                    .format(ICON_ZIP_FILENAME)
                )

            self.iconsLoaded = True

        except Exception as e:

            Domoticz.Error(
                "Could not load custom icons ({}) - devices will use the default Alert icon."
                .format(e)
            )

            self.iconsLoaded = False

    def onStop(self):

        Domoticz.Debug("onStop called")
        Domoticz.Debugging(0)

    def onCommand(self, Unit, Command, Level, Hue):

        Domoticz.Debug(
            "onCommand called for Unit " +
            str(Unit) +
            ": Parameter '" +
            str(Command) +
            "', Level: " +
            str(Level)
        )

    def onHeartbeat(self):

        # (fixed in 1.6.1, extended in 1.7.0 for multi-region: guard against
        # onStart having failed before any Meteo instance was created.)

        if not self.meteoList:

            Domoticz.Error(
                "Plugin not initialized (no Meteo instances) - check onStart errors above, skipping heartbeat"
            )

            return

        now = datetime.now()

        if now < self.nextpoll:
            return

        # fetch the feed ONCE per heartbeat and share it across all
        # configured regions, instead of each region doing its own
        # redundant HTTP fetch of what is the same feed content.

        try:

            feed, rawData = meteo.fetchFeed(
                self.rssUrl,
                Meteo.FEED_FETCH_TIMEOUT_SECONDS
            )

        except Exception as e:

            Domoticz.Error(
                "Error #{} on reading feed: {}".format(
                    self.errorCounter,
                    e
                )
            )

            self.errorCounter += 1
            self.nextpoll = now

            errTxt = str(e)

            for i, mt in enumerate(self.meteoList):

                mt.setError(errTxt)

                todayUnit, tomorrowUnit = unitsForRegion(i)

                updateDevice(
                    todayUnit,
                    4,
                    errTxt,
                    name=deviceNameForRegion(
                        i,
                        tomorrow=False
                    )
                )

                updateDevice(
                    tomorrowUnit,
                    4,
                    errTxt,
                    name=deviceNameForRegion(
                        i,
                        tomorrow=True
                    )
                )

            updateDevice(
                3,
                1,
                "ERROR #{}: {}".format(
                    self.errorCounter,
                    errTxt
                )
            )

            # (fixed in 1.6.1: was `if(self.errorCounter % 10):` which is
            # truthy for every count EXCEPT exact multiples of 10 - i.e. it
            # backed off on almost every error instead of only every 10th
            # one. Correct check needs `== 0`.)

            if self.errorCounter % 10 == 0:

                for mt in self.meteoList:
                    mt.reset()

                backoffIndex = min(
                    (self.errorCounter // 10) - 1,
                    len(BACKOFF_STEPS_MINUTES) - 1
                )

                backoffMinutes = BACKOFF_STEPS_MINUTES[backoffIndex]

                Domoticz.Error(
                    "got {} times an error, wait {} min before try again"
                    .format(
                        self.errorCounter,
                        backoffMinutes
                    )
                )

                self.nextpoll = (
                    now +
                    timedelta(
                        minutes=backoffMinutes
                    )
                )

            Domoticz.Debug(
                "----------------------------------------------------"
            )

            return

        # fetch succeeded - process each region against the shared feed

        self.errorCounter = 0

        self.lastSuccessfulUpdate = now

        self.nextpoll = (
            now +
            timedelta(
                seconds=self.pollinterval
            )
        )

        updateDevice(
            3,
            0,
            "OK"
        )

        updateDevice(
            4,
            0,
            "{:%Y-%m-%d %H:%M:%S}".format(
                self.lastSuccessfulUpdate
            ),
            alwaysUpdate=True
        )

        for i, mt in enumerate(self.meteoList):

            todayUnit, tomorrowUnit = unitsForRegion(i)

            try:

                mt.processFetchedFeed(feed)

            except Exception as e:

                Domoticz.Error(
                    "Error processing region '{}': {}".format(
                        mt.rssCode,
                        e
                    )
                )

                mt.setError(e)

            if mt.hasError:

                updateDevice(
                    todayUnit,
                    4,
                    str(mt.errorMsg),
                    name=deviceNameForRegion(
                        i,
                        tomorrow=False
                    )
                )

                updateDevice(
                    tomorrowUnit,
                    4,
                    str(mt.errorMsg),
                    name=deviceNameForRegion(
                        i,
                        tomorrow=True
                    )
                )

            elif mt.needUpdate is True:

                todayImage = (
                    mt.getDayIconKey(0)
                    if self.iconsLoaded
                    else None
                )

                tomorrowImage = (
                    mt.getDayIconKey(1)
                    if self.iconsLoaded
                    else None
                )

                updateDevice(
                    todayUnit,
                    mt.todayLevel,
                    mt.todayDetail,
                    name=deviceNameForRegion(
                        i,
                        tomorrow=False
                    ),
                    imageName=todayImage
                )

                updateDevice(
                    tomorrowUnit,
                    mt.tomorrowLevel,
                    mt.tomorrowDetail,
                    name=deviceNameForRegion(
                        i,
                        tomorrow=True
                    ),
                    imageName=tomorrowImage
                )

        Domoticz.Debug(
            "----------------------------------------------------"
        )


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

    _plugin.onCommand(
        Unit,
        Command,
        Level,
        Hue
    )


def onHeartbeat():

    global _plugin

    _plugin.onHeartbeat()


#############################################################################
#                   common functions                                       #
#############################################################################


def unitsForRegion(index):

    '''maps a region's index in self.meteoList to its (today, tomorrow)
    Domoticz Unit numbers. Index 0 (the primary/Mode2 region) always uses
    Units 1/2, unchanged since before multi-region support, so existing
    installs upgrading to 1.7.0 keep their existing device IDs. Units 3/4
    are reserved for the shared Plugin Status / Last Successful Update
    devices. Additional regions start at Unit 5, two Units each.
    Arguments:
        index {int} -- position in self.meteoList
    Returns:
        (int, int) -- (todayUnit, tomorrowUnit)
    '''

    if index == 0:

        return 1, 2

    return (
        5 + (index - 1) * 2,
        6 + (index - 1) * 2
    )


def regionCodeForIndex(index):

    '''returns the configured RSS region code for a region index.

    The region code is used as part of the stable Domoticz device name
    so that multiple configured regions can always be distinguished.

    Arguments:
        index {int} -- position in self.meteoList

    Returns:
        str -- configured region code
    '''

    if index < 0 or index >= len(_plugin.meteoList):

        return "REGION{}".format(index + 1)

    return _plugin.meteoList[index].rssCode


def deviceNameForRegion(index, tomorrow=False):

    '''returns the stable Domoticz device name for a region.

    Region codes are deliberately included in the names of ALL
    Today/Tomorrow devices, including the primary region.

    Arguments:
        index {int} -- position in self.meteoList
        tomorrow {bool} -- True for the Tomorrow device

    Returns:
        str -- stable Domoticz device name
    '''

    code = regionCodeForIndex(index)

    if tomorrow:

        return "Tomorrow ({})".format(code)

    return "Today ({})".format(code)


def DumpConfigToLog():

    '''just dumps the configuration to log.
    '''

    for x in Parameters:

        if Parameters[x] != "":

            Domoticz.Debug(
                "'" +
                x +
                "':'" +
                str(Parameters[x]) +
                "'"
            )

    Domoticz.Debug(
        "Device count: " +
        str(len(Devices))
    )

    for x in Devices:

        Domoticz.Debug(
            "Device:           " +
            str(x) +
            " - " +
            str(Devices[x])
        )

        Domoticz.Debug(
            "Device ID:       '" +
            str(Devices[x].ID) +
            "'"
        )

        Domoticz.Debug(
            "Device Name:     '" +
            Devices[x].Name +
            "'"
        )

        Domoticz.Debug(
            "Device nValue:    " +
            str(Devices[x].nValue)
        )

        Domoticz.Debug(
            "Device sValue:   '" +
            Devices[x].sValue +
            "'"
        )

        Domoticz.Debug(
            "Device LastLevel: " +
            str(Devices[x].LastLevel)
        )

    return


#############################################################################
#                       Device specific functions                           #
#############################################################################


def createDevices(regionCount):

    '''creates the Today/Tomorrow device pair for each configured region,
    plus the shared Plugin Status / Last Successful Update devices, if
    they don't already exist.

    Region codes are included in the device names for every region,
    including the primary region. Existing devices retain their Unit
    numbers and are renamed during onStart().

    Arguments:
        regionCount {int} -- number of configured regions (>= 1)
    '''

    # ------------------------------------------------------------------
    # Create one Today/Tomorrow pair for every configured region.
    #
    # Unit numbering remains unchanged for backward compatibility:
    #
    #   Region 0 -> Units 1 / 2
    #   Region 1 -> Units 5 / 6
    #   Region 2 -> Units 7 / 8
    #   ...
    #
    # Units 3 / 4 remain reserved for Plugin Status /
    # Last Successful Update.
    # ------------------------------------------------------------------

    for i in range(regionCount):

        todayUnit, tomorrowUnit = unitsForRegion(i)

        todayName = deviceNameForRegion(
            i,
            tomorrow=False
        )

        tomorrowName = deviceNameForRegion(
            i,
            tomorrow=True
        )

        if todayUnit not in Devices:

            Domoticz.Device(
                Name=todayName,
                Unit=todayUnit,
                TypeName="Alert",
                Used=1
            ).Create()

            Domoticz.Log(
                "Devices[{}] (Today, {}) created."
                .format(
                    todayUnit,
                    regionCodeForIndex(i)
                )
            )

        if tomorrowUnit not in Devices:

            Domoticz.Device(
                Name=tomorrowName,
                Unit=tomorrowUnit,
                TypeName="Alert",
                Used=1
            ).Create()

            Domoticz.Log(
                "Devices[{}] (Tomorrow, {}) created."
                .format(
                    tomorrowUnit,
                    regionCodeForIndex(i)
                )
            )

    if 3 not in Devices:

        Domoticz.Device(
            Name="Plugin Status",
            Unit=3,
            TypeName="Alert",
            Used=1
        ).Create()

        Domoticz.Log(
            "Devices[3] (Plugin Status) created."
        )

    if 4 not in Devices:

        Domoticz.Device(
            Name="Last Successful Update",
            Unit=4,
            TypeName="Text",
            Used=1
        ).Create()

        Domoticz.Log(
            "Devices[4] (Last Successful Update) created."
        )


def updateDevice(
    Unit,
    highestLevel,
    alarmData,
    name='',
    alwaysUpdate=False,
    imageName=None
):

    '''update a device - means today or tomorrow (or status/last-update),
    with given data. If there are changes and the device exists.
    Arguments:
        Unit {int} -- Domoticz Unit number
        highestLevel {int} -- the maximum warning level for that day
        alarmData {str} -- data to show in that device, aka text
    Optional Arguments:
        name {str} -- optional: to set the device's display name
        alwaysUpdate {bool} -- optional: ignore current status/needs update
        imageName {str} -- optional: custom icon name from Images, e.g.
                            "MeteoAlarmEUAtomThunderstormL3". Ignored if
                            not found in Images - never an error.
    '''

    if Unit not in Devices:

        Domoticz.Error(
            "Devices[{}] is unknown. So we cannot update it."
            .format(Unit)
        )

        return

    kwargs = {}

    if imageName and imageName in Images:

        kwargs['Image'] = Images[imageName].ID

    if (
        (alarmData != Devices[Unit].sValue)
        or
        (int(highestLevel) != Devices[Unit].nValue)
        or
        alwaysUpdate is True
    ):

        if len(name) <= 0:

            Devices[Unit].Update(
                int(highestLevel),
                str(alarmData),
                **kwargs
            )

        else:

            Devices[Unit].Update(
                int(highestLevel),
                str(alarmData),
                Name=name,
                **kwargs
            )

        Domoticz.Log(
            "BLZ: Awareness Updated to: {} value: {}"
            .format(
                alarmData,
                highestLevel
            )
        )

    else:

        Domoticz.Log(
            "BLZ: Awareness Remains Unchanged"
        )
