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

            1.7.2: "quiet and safe". A feed problem is no longer shown as
                  a red weather alert: Today/Tomorrow keep their last
                  values and go grey only once the data is stale (3 poll
                  intervals); Plugin Status carries the failure (green OK,
                  orange retrying, red failing/config error, grey
                  starting). Settings are validated once at start - a
                  config error is reported once and polling is skipped.
                  Time-based retry backoff replaces the 10-retries-per-
                  cycle loop. HTTP-200 garbage pages are rejected instead
                  of reading as "all clear". Today/Tomorrow are re-split
                  at midnight without a new request. Restarts no longer
                  wipe device values; device names are set once and never
                  rewritten on update (names you chose yourself are kept);
                  the publish time moved from the name into the device
                  text. Default poll interval is now 30 minutes. See
                  CHANGELOG.md for full detail.

            1.7.3: community release, no change to what the plugin does.
                  Code of Conduct, contributing guide, security policy,
                  accessibility statement, issue forms and a pull request
                  template; README gained a warning-levels table;
                  testCommunity.py checks the documents and forms. See
                  CHANGELOG.md.

<plugin key="MeteoAlarmEU-Atom" name="Meteo Alarm EU RSS Reader Atom" author="belze,ycahome,janreimen" version="1.7.3" wikilink="" externallink="https://github.com/janreimen/Domoticz-MeteoAlarmEU-Atom">
    <description>
        <h2>Meteo Alarm EU RSS Reader eXtended</h2><br/>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>shows warnings for today and tomorrow, for one or more regions</li>
            <li>using domoticz alarm level to signal the risk</li>
            <li>detail level can be chosen</li>
            <li>supports english, german, swedish, french, spanish, finnish, luxembourgish</li>
            <li>meteo publish time is shown at the end of the device text</li>
            <li>a feed problem never shows up as a weather alert - see Plugin Status</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>today / tomorrow - warnings for each configured region, with the region code in the device name</li>
            <li>Plugin Status - green OK, orange retrying, red failing or configuration error, grey starting</li>
            <li>Last Successful Update - time of the last clean feed fetch</li>
        </ul>
        <h3>Hint</h3>
        First visit -><a href="https://feeds.meteoalarm.org/">
        Meteo</a> to choose your region and get rss-Feed link
    </description>
    <params>
        <param field="Mode1" label="RSSFeed" width="400px" required="true" default="https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-luxembourg"/>
        <param field="Mode2" label="RSSCode(s) (comma-separated regions)" width="400px" required="true" default="LU002, LU001"/>
        <param field="Mode3" label="Update every x minutes" width="200px" required="true" default="30"/>
        <param field="Mode4" label="Debug" width="75px">
            <options>
                <option label="False" value="Normal" selected="selected"/>
                <option label="True" value="Debug"/>
            </options>
        </param>
        <param field="Mode5" label="Details and Language for Status" width="200px"
        title="here you can choose if more details from rss should be shown and if so - which language to use">
            <options>
                <option label="NO_DETAIL" value="no_detail"/>
                <option label="Details using domoticz lang" value="detail_dom_lang"/>
                <option label="Details in English" value="English"/>
                <option label="Details auf Deutsch" value="German"/>
                <option label="Details på Svenska" value="Swedish"/>
                <option label="Details in Spanish" value="Spanish"/>
                <option label="Details in French" value="French"/>
                <option label="Details in Finnish" value="Finnish"/>
                <option label="Detailer op Lëtzebuergesch" value="Luxembourgish" selected="selected"/>
            </options>
        </param>
        <param field="Mode6" label="Show Alarm Icons" width="200px"
        title="as of 1.7.0 this controls the plugin's own bundled severity+type icon set, since the feed itself no longer provides icons">
            <options>
                <option label="NO_ICON" value="icon_no" selected="selected"/>
                <option label="inline icon" value="icon_inline"/>
                <option label="inline icon with detail" value="icon_inline_detail"/>
            </options>
        </param>
    </params>
</plugin>
"""

import os
import re
from datetime import datetime, timedelta

import meteo
from meteo import Meteo

try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz

# Domoticz injects Parameters, Settings, Devices and Images into this module.

# If running on Windows or Synology and downloaded modules aren't found,
# add the relevant site-packages path here, e.g.:
# import sys; sys.path.append('/path/to/site-packages')

# polling interval (minutes): default for new hardware and the fallback when
# Mode3 is missing or invalid, plus the accepted range
DEFAULT_POLL_MINUTES = 30
MIN_POLL_MINUTES = 5
MAX_POLL_MINUTES = 1440

# wait (seconds) after the 1st, 2nd, ... consecutive failed fetch; the last
# step repeats. A wait is never longer than the normal poll interval.
RETRY_STEPS_SECONDS = [60, 120, 300, 600, 1800, 3600]

# Today/Tomorrow turn grey once no fetch has succeeded for this many poll
# intervals - an old all-clear must not linger for days
STALE_AFTER_POLLS = 3

# Alert device levels
LEVEL_GREY = 0
LEVEL_GREEN = 1
LEVEL_YELLOW = 2
LEVEL_ORANGE = 3
LEVEL_RED = 4

# shared (non-region) device units
STATUS_UNIT = 3
LASTUPDATE_UNIT = 4

# filename of the bundled custom icon zip, expected alongside plugin.py
ICON_ZIP_FILENAME = "meteoalarm_icons.zip"

# one representative image name used to check whether icons are already
# loaded, to avoid recreating them on every onStart()
ICON_PROBE_NAME = "MeteoAlarmEUAtomWindL1"


def parsePollMinutes(raw):
    '''turn the Mode3 setting into a usable polling interval.

    Returns:
        (int, list[str]) -- minutes and the problems found (each one is
        logged by the caller); an invalid value falls back to the default,
        an out-of-range value is clamped.
    '''
    problems = []
    try:
        minutes = int(raw)
    except (ValueError, TypeError):
        minutes = DEFAULT_POLL_MINUTES
        problems.append("Invalid polling interval parameter '{}', falling back to {} minutes"
                        .format(raw, minutes))
    if minutes < MIN_POLL_MINUTES:
        minutes = MIN_POLL_MINUTES
        problems.append("Specified polling interval too short: changed to {} minutes".format(MIN_POLL_MINUTES))
    elif minutes > MAX_POLL_MINUTES:
        minutes = MAX_POLL_MINUTES
        problems.append("Specified polling interval too long: changed to {} minutes (1 day)"
                        .format(MAX_POLL_MINUTES))
    return minutes, problems


class BasePlugin:

    def __init__(self):
        self.debug = False
        self.iconsLoaded = False
        self._resetState()
        return

    def _resetState(self):
        '''runtime state; also called from onStart so a restarted hardware
        never inherits counters from its previous run.'''
        self.errorCounter = 0           # consecutive failed fetches
        self.lastError = None           # text of the previous failure
        self.nextpoll = datetime.now()
        self.meteoList = []             # one Meteo instance per configured region
        self.rssUrl = None
        self.pollinterval = DEFAULT_POLL_MINUTES * 60
        self.startedAt = datetime.now()
        self.lastSuccessfulUpdate = None
        self.lastFeed = None            # last good feed, re-used at midnight
        self.lastAppliedDate = None     # date the devices were last computed for
        self.dataStale = False
        self.configError = None

    # ------------------------------------------------------------------
    # start / stop
    # ------------------------------------------------------------------

    def onStart(self):
        self._resetState()

        if Parameters["Mode4"] == 'Debug':
            self.debug = True
            Domoticz.Debugging(1)
            DumpConfigToLog()
        else:
            self.debug = False
            Domoticz.Debugging(0)

        Domoticz.Debug("onStart called")

        minutes, problems = parsePollMinutes(Parameters.get("Mode3"))
        for problem in problems:
            Domoticz.Error(problem)
        self.pollinterval = minutes * 60
        Domoticz.Log("Using polling interval of {} seconds".format(self.pollinterval))

        # validate the settings once. A configuration error can never be fixed
        # by retrying, so it is reported ONCE and polling is skipped.
        self.rssUrl = str(Parameters.get("Mode1", "")).strip()
        errors, warnings, codes = meteo.validateConfig(self.rssUrl, Parameters.get("Mode2", ""))
        for warning in warnings:
            Domoticz.Error(warning)

        if not errors:
            Domoticz.Log("Monitoring {} region(s): {}".format(len(codes), ", ".join(codes)))
            for code in codes:
                try:
                    self.meteoList.append(Meteo(
                        self.rssUrl,
                        rssCode=code,
                        domLangSetting=Settings["Language"],
                        detailSetting=Parameters["Mode5"],
                        iconSetting=Parameters["Mode6"],
                        locationName=Parameters["Name"]))
                except Exception as e:
                    errors.append("Failed to initialize region '{}': {}".format(code, e))

        if errors:
            self.configError = "; ".join(errors)
            for error in errors:
                Domoticz.Error("Configuration error: " + error)
            Domoticz.Error("Polling is disabled until the hardware settings are corrected - "
                           "edit the hardware, fix the setting and press Update.")
            self.meteoList = []
            newUnits = createDevices(0)
            self._initDevices(newUnits)
            updateDevice(STATUS_UNIT, LEVEL_RED, "CONFIG ERROR: " + self.configError)
            return

        if self.debug is True:
            self.meteoList[0].dumpMeteoConfig()

        # load the bundled severity+type icon set. This is never allowed
        # to prevent the plugin from working - any failure here just
        # means devices fall back to the default Alert icon.
        self._loadIcons()

        newUnits = createDevices(len(self.meteoList))
        self._initDevices(newUnits)
        self._renameLegacyDevices()

    def _initDevices(self, newUnits):
        '''(1.7.2) a restart must not wipe what the devices already show.
        Only devices created just now get a placeholder; Plugin Status goes
        to "Starting" (grey) because its real state is unknown until the
        first fetch has finished.'''
        for unit in newUnits:
            if unit == LASTUPDATE_UNIT:
                updateDevice(unit, LEVEL_GREY, "never", alwaysUpdate=True)
            elif unit != STATUS_UNIT:
                updateDevice(unit, LEVEL_GREY, "No Data", alwaysUpdate=True)
        updateDevice(STATUS_UNIT, LEVEL_GREY, "Starting")

    def _renameLegacyDevices(self):
        '''(1.7.2) bring Today/Tomorrow devices to their region-qualified
        names ONCE per start - never on update. A device whose name does not
        look plugin-generated was renamed by the user and is left alone.'''
        for i in range(len(self.meteoList)):
            for unit, tomorrow in zip(unitsForRegion(i), (False, True)):
                if unit not in Devices:
                    continue
                desired = deviceNameForRegion(i, tomorrow)
                current = shortDeviceName(Devices[unit].Name)
                if current == desired:
                    continue
                if not isPluginGeneratedName(current):
                    Domoticz.Debug("Device {} has the custom name '{}' - leaving it alone"
                                   .format(unit, current))
                    continue
                Devices[unit].Update(Devices[unit].nValue, Devices[unit].sValue, Name=desired)
                Domoticz.Log("Renamed device {} from '{}' to '{}'".format(unit, current, desired))

    def _loadIcons(self):
        try:
            zipPath = os.path.join(Parameters.get("HomeFolder", ""), ICON_ZIP_FILENAME)
            if not os.path.exists(zipPath):
                Domoticz.Debug("Icon zip not found at {} - devices will use the default Alert icon."
                               .format(zipPath))
                self.iconsLoaded = False
                return

            if ICON_PROBE_NAME not in Images:
                Domoticz.Image(Filename=ICON_ZIP_FILENAME).Create()
                Domoticz.Log("Custom severity/type icon set loaded from {}.".format(ICON_ZIP_FILENAME))
            Domoticz.Debug("Icon probe '{}' registered in Images: {}"
                           .format(ICON_PROBE_NAME, ICON_PROBE_NAME in Images))
            self.iconsLoaded = True

        except Exception as e:
            Domoticz.Error("Could not load custom icons ({}) - devices will use the default Alert icon."
                           .format(e))
            self.iconsLoaded = False

    def onStop(self):
        Domoticz.Debug("onStop called")
        Domoticz.Debugging(0)

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command)
                       + "', Level: " + str(Level))

    # ------------------------------------------------------------------
    # heartbeat
    # ------------------------------------------------------------------

    def onHeartbeat(self):
        # a configuration error was reported once in onStart - nothing to poll
        if self.configError is not None or not self.meteoList:
            return

        now = datetime.now()
        self._rolloverIfNeeded(now)

        # staleness is judged on every heartbeat, not only when a retry
        # happens - otherwise it could lag by up to a whole retry wait
        if self.errorCounter and not self.dataStale and now - self._lastGood() >= self._staleLimit():
            self._updateFailureState(now)

        if now < self.nextpoll:
            return

        # fetch the feed ONCE per heartbeat and share it across all
        # configured regions, instead of each region doing its own
        # redundant HTTP fetch of what is the same feed content.
        try:
            feed, rawData = meteo.fetchFeed(self.rssUrl, Meteo.FEED_FETCH_TIMEOUT_SECONDS)
        except Exception as e:
            self._onFetchFailed(now, e)
            return

        self._onFetchOk(now, feed)
        Domoticz.Debug("----------------------------------------------------")

    def _rolloverIfNeeded(self, now):
        '''(1.7.2) Today/Tomorrow are computed relative to "now", so after
        midnight the old values are wrong until the next fetch - up to a
        whole poll interval. Re-split the cached feed instead (no request).'''
        if self.lastFeed is None or self.dataStale or self.lastAppliedDate == now.date():
            return
        Domoticz.Log("Date changed - re-evaluating the last fetched feed for the new day (no new request)")
        self._applyFeed(self.lastFeed, now)

    def _staleLimit(self):
        return timedelta(seconds=self.pollinterval * STALE_AFTER_POLLS)

    def _retryWait(self, attempt):
        step = RETRY_STEPS_SECONDS[min(attempt - 1, len(RETRY_STEPS_SECONDS) - 1)]
        return min(step, self.pollinterval)

    def _onFetchFailed(self, now, error):
        '''(1.7.2) a failed fetch is a PLUGIN problem, not a weather event:
        Today/Tomorrow keep their last values (until they go stale) and the
        failure is shown on Plugin Status only.'''
        text = str(error)
        self.errorCounter += 1
        wait = self._retryWait(self.errorCounter)
        self.nextpoll = now + timedelta(seconds=wait)

        # log on the first failure, when the message changes and while the
        # wait escalates; repeats at the longest wait go to debug
        if (self.errorCounter == 1 or text != self.lastError
                or self.errorCounter <= len(RETRY_STEPS_SECONDS)):
            Domoticz.Error("Feed fetch failed (attempt {}): {} - retrying in {} s"
                           .format(self.errorCounter, text, wait))
        else:
            Domoticz.Debug("Feed fetch failed again (attempt {}): {}".format(self.errorCounter, text))
        self.lastError = text

        self._updateFailureState(now)

    def _lastGood(self):
        return self.lastSuccessfulUpdate or self.startedAt

    def _updateFailureState(self, now):
        '''orange while the shown data is still fresh enough, red (and
        Today/Tomorrow grey) once it is older than the stale limit.'''
        lastGood = self._lastGood()
        if now - lastGood >= self._staleLimit():
            self._markStale(lastGood, now)
            updateDevice(STATUS_UNIT, LEVEL_RED,
                         "FAILING since {}: {}".format(shortTime(lastGood, now), self.lastError))
        else:
            updateDevice(STATUS_UNIT, LEVEL_ORANGE,
                         "Retrying (attempt {}): {}".format(self.errorCounter, self.lastError))

    def _markStale(self, lastGood, now):
        if not self.dataStale:
            self.dataStale = True
            Domoticz.Error("No successful feed update since {} - marking Today/Tomorrow as stale (grey)"
                           .format(shortTime(lastGood, now)))
        for i, mt in enumerate(self.meteoList):
            # reset() forces a full device refresh once the feed is back
            mt.reset()
            for unit in unitsForRegion(i):
                updateDevice(unit, LEVEL_GREY, "No data - feed unreachable since {}".format(shortTime(lastGood, now)))

    def _onFetchOk(self, now, feed):
        if self.errorCounter:
            Domoticz.Log("Feed fetch recovered after {} failed attempt(s)".format(self.errorCounter))
        self.errorCounter = 0
        self.lastError = None
        self.dataStale = False
        self.lastSuccessfulUpdate = now
        self.nextpoll = now + timedelta(seconds=self.pollinterval)
        self.lastFeed = feed

        problems = self._applyFeed(feed, now)

        if problems:
            updateDevice(STATUS_UNIT, LEVEL_ORANGE, "Feed OK, but processing failed: " + "; ".join(problems))
        else:
            updateDevice(STATUS_UNIT, LEVEL_GREEN, "OK")
        updateDevice(LASTUPDATE_UNIT, LEVEL_GREY, "{:%Y-%m-%d %H:%M:%S}".format(now), alwaysUpdate=True)

    def _applyFeed(self, feed, now):
        '''process the feed for every region and update the devices.

        Returns:
            list[str] -- one message per region that could not be processed.
            Such a region keeps its previous device values; it never turns
            red because of a plugin-side problem.'''
        problems = []
        for i, mt in enumerate(self.meteoList):
            todayUnit, tomorrowUnit = unitsForRegion(i)
            try:
                mt.processFetchedFeed(feed)
            except Exception as e:
                Domoticz.Error("Error processing region '{}': {}".format(mt.rssCode, e))
                mt.setError(e)

            if mt.hasError:
                problems.append("{}: {}".format(mt.rssCode, mt.errorMsg))
            elif mt.needUpdate is True:
                todayImage = mt.getDayIconKey(0) if self.iconsLoaded else None
                tomorrowImage = mt.getDayIconKey(1) if self.iconsLoaded else None
                updateDevice(todayUnit, mt.todayLevel, mt.todayDetail, imageName=todayImage)
                updateDevice(tomorrowUnit, mt.tomorrowLevel, mt.tomorrowDetail, imageName=tomorrowImage)
        self.lastAppliedDate = now.date()
        return problems


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
#                   common functions                                       #
#############################################################################


def shortTime(moment, now):
    '''"HH:MM" for today, "D.M. HH:MM" for another day.'''
    if moment.date() == now.date():
        return "{:%H:%M}".format(moment)
    return "{:%d.%m. %H:%M}".format(moment)


def unitsForRegion(index):
    '''maps a region's index in self.meteoList to its (today, tomorrow)
    Domoticz Unit numbers. Index 0 (the primary/first Mode2 region) always
    uses Units 1/2, unchanged since before multi-region support, so existing
    installs keep their existing device IDs. Units 3/4 are reserved for the
    shared Plugin Status / Last Successful Update devices. Additional
    regions start at Unit 5, two Units each.

    Arguments:
        index {int} -- position in self.meteoList

    Returns:
        (int, int) -- (todayUnit, tomorrowUnit)
    '''
    if index == 0:
        return 1, 2
    return 5 + (index - 1) * 2, 6 + (index - 1) * 2


def regionCodeForIndex(index):
    '''returns the configured region code for a region index.'''
    if index < 0 or index >= len(_plugin.meteoList):
        return "REGION{}".format(index + 1)
    return _plugin.meteoList[index].rssCode


def deviceNameForRegion(index, tomorrow=False):
    '''returns the stable Domoticz device name for a region, e.g.
    "Today (LU002)". Region codes are part of the names of ALL Today/Tomorrow
    devices, including the primary region.'''
    code = regionCodeForIndex(index)
    return "Tomorrow ({})".format(code) if tomorrow else "Today ({})".format(code)


def shortDeviceName(fullName):
    '''Domoticz may report a plugin device as "<hardware name> - <name>";
    return the part after the hardware prefix.'''
    prefix = "{} - ".format(Parameters.get("Name", ""))
    if prefix != " - " and str(fullName).startswith(prefix):
        return str(fullName)[len(prefix):]
    return str(fullName)


def isPluginGeneratedName(name):
    '''True for every shape this plugin ever gave a Today/Tomorrow device:
    "Today", "Today (LU002)", and the feed-title form "Today: Luxembourg
    (14:05)" / "Heute: ERROR!!!" of 1.7.0, in any supported language. A
    name the user chose themselves does not match and is never rewritten.'''
    words = set(Meteo.AWT_TRANSLATION[200]) | set(Meteo.AWT_TRANSLATION[201])
    pattern = r'^(?:{})(?:\s*\(.*\)|:.*)?$'.format('|'.join(re.escape(w) for w in sorted(words)))
    return re.match(pattern, str(name).strip(), re.IGNORECASE) is not None


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


#############################################################################
#                       Device specific functions                           #
#############################################################################


def createDevices(regionCount):
    '''creates the Today/Tomorrow device pair for each configured region,
    plus the shared Plugin Status / Last Successful Update devices, if
    they don't already exist. Existing devices keep their Unit numbers.

    Arguments:
        regionCount {int} -- number of configured regions (0 only when the
                             configuration is invalid and just the status
                             devices are wanted)

    Returns:
        list[int] -- the Units created by this call
    '''
    created = []

    # Unit numbering stays unchanged for backward compatibility:
    #   Region 0 -> Units 1 / 2,  Region 1 -> Units 5 / 6,  Region 2 -> 7 / 8 ...
    #   Units 3 / 4 -> Plugin Status / Last Successful Update
    for i in range(regionCount):
        todayUnit, tomorrowUnit = unitsForRegion(i)
        for unit, tomorrow in ((todayUnit, False), (tomorrowUnit, True)):
            if unit not in Devices:
                Domoticz.Device(Name=deviceNameForRegion(i, tomorrow), Unit=unit,
                                TypeName="Alert", Used=1).Create()
                created.append(unit)
                Domoticz.Log("Devices[{}] ({}, {}) created."
                             .format(unit, "Tomorrow" if tomorrow else "Today", regionCodeForIndex(i)))

    if STATUS_UNIT not in Devices:
        Domoticz.Device(Name="Plugin Status", Unit=STATUS_UNIT, TypeName="Alert", Used=1).Create()
        created.append(STATUS_UNIT)
        Domoticz.Log("Devices[{}] (Plugin Status) created.".format(STATUS_UNIT))

    if LASTUPDATE_UNIT not in Devices:
        Domoticz.Device(Name="Last Successful Update", Unit=LASTUPDATE_UNIT, TypeName="Text", Used=1).Create()
        created.append(LASTUPDATE_UNIT)
        Domoticz.Log("Devices[{}] (Last Successful Update) created.".format(LASTUPDATE_UNIT))

    return created


def updateDevice(Unit, highestLevel, alarmData, alwaysUpdate=False, imageName=None):
    '''update a device - means today or tomorrow (or status/last-update),
    with given data, if there are changes and the device exists. The device
    NAME is never touched here (1.7.2): names are set when a device is
    created, and renamed only by the one-time migration in onStart.

    Arguments:
        Unit {int} -- Domoticz Unit number
        highestLevel {int} -- the maximum warning level for that day
        alarmData {str} -- data to show in that device, aka text

    Optional Arguments:
        alwaysUpdate {bool} -- optional: ignore current status/needs update
        imageName {str} -- optional: custom icon name from Images, e.g.
                            "MeteoAlarmEUAtomThunderstormL3". Ignored if
                            not found in Images - never an error.
    '''
    if Unit not in Devices:
        Domoticz.Error("Devices[{}] is unknown. So we cannot update it.".format(Unit))
        return

    kwargs = {}
    if imageName and imageName in Images:
        kwargs['Image'] = Images[imageName].ID

    if ((alarmData != Devices[Unit].sValue) or (int(highestLevel) != Devices[Unit].nValue)
            or alwaysUpdate is True):
        Devices[Unit].Update(int(highestLevel), str(alarmData), **kwargs)
        Domoticz.Debug("Device {} updated to level {}: {}".format(Unit, highestLevel, alarmData))
    else:
        Domoticz.Debug("Device {} unchanged".format(Unit))
