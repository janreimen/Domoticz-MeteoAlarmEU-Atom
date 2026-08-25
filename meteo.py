# moved logic of Meteo rss warning to extra class
#
# 1.6.3 note: the live meteoalarm.org Atom feed no longer embeds an HTML
# table with per-language text blocks and icon <img> tags inside each
# entry's <description> (the format this file originally parsed). It now
# publishes structured CAP fields directly (cap:event, cap:severity,
# cap:onset, cap:expires, etc.) with no per-entry icon and no embedded
# multi-language text. This file was rewritten against the real current
# feed structure (verified by fetching and inspecting it directly) rather
# than the old HTML-scraping approach, which would throw on every matching
# entry against live data (KeyError on the now-nonexistent 'description'
# field).
import re
from datetime import datetime, timedelta
from time import mktime

# import sys
# sys.path
# sys.path.append('/usr/lib/python3/dist-packages')
# synology
# sys.path.append('/volume1/@appstore/py3k/usr/local/lib/python3.5/site-packages')
# windows
# sys.path.append('C:\\Program Files (x86)\\Python37-32\\Lib\\site-packages')

import feedparser
import urllib.request
import urllib.error
import socket

try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz


def parseCapIsoDate(value):
    """parse an ISO-8601 timestamp as used in cap:onset/cap:expires/etc,
    converting to the system's local timezone if the value carries an
    explicit UTC offset.

    Arguments:
        value {str} -- e.g. '2026-08-23T15:00:00+00:00' or with trailing 'Z'

    Returns:
        datetime | None -- parsed, timezone-aware where possible, else None
    """
    if not value:
        return None
    try:
        v = str(value).strip()
        if v.endswith('Z'):
            v = v[:-1] + '+00:00'
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt
    except Exception:
        return None


class Meteo:
    # ####################################
    # Common definitions
    # maximum length (chars) of the combined per-day summary text
    MAX_SHOWN_DETAIL_LENGTH = 200
    # show pub date of rss in name
    SHOW_DATE_IN_NAME = True
    # timeout (seconds) for fetching the feed - previously unbounded,
    # a hung connection would block the whole Domoticz heartbeat cycle
    FEED_FETCH_TIMEOUT_SECONDS = 15

    AWT_TRANSLATION = {
        # idx: [English, German, Swedish, French, Spanish, Finnish]
        1: ["Wind", "Wind", "Wind", "Vent", "Viento", "Tuuli"],
        2: ["Snow/Ice", "Schnee/Eis", "Snö/Is", "Neige/Verglas", "Nieve/Hielo", "Lumi/Jää"],
        3: ["ThunderStorm", "Gewitter", "Åska", "Orage", "Tormenta", "Ukkonen"],
        4: ["Fog", "Nebel", "Dimma", "Brouillard", "Niebla", "Sumu"],
        5: ["High Temp", "Hohe Temp.", "Hög temp.", "Températures élevées", "Temperatura alta", "Korkea lämpötila"],
        6: ["Low Temp", "Niedrige Temp.", "Låg temp.", "Températures basses", "Temperatura baja", "Matala lämpötila"],
        7: ["Coastal Event", "Küstenereignis", "Kusthändelse", "Phénomène côtier", "Fenómeno costero", "Rannikkoilmiö"],
        8: ["Forestfire", "Waldbrand", "Skogsbrand", "Feu de forêt", "Incendio forestal", "Metsäpalo"],
        9: ["Avalanches", "Lawinen", "Laviner", "Avalanches", "Avalanchas", "Lumivyöryt"],
        10: ["Rain", "Regen", "Regn", "Pluie", "Lluvia", "Sade"],
        11: ["Flood", "Flut", "Översvämning", "Inondation", "Inundación", "Tulva"],
        12: ["Rain-Flood", "Regen-Flut", "Regn-Översvämning", "Pluie-Inondation", "Lluvia-Inundación", "Sade-Tulva"],
        99: ["No special awareness required", "Allet knorke!", "Ingen särskild uppmärksamhet krävs",
             "Aucune vigilance particulière requise", "No se requiere atención especial",
             "Ei erityistä varautumista vaadita"],
        200: ["Today", "Heute", "Idag", "Aujourd'hui", "Hoy", "Tänään"],
        201: ["Tomorrow", "Morgen", "Imorgon", "Demain", "Mañana", "Huomenna"]
    }

    # dict for switch dom language to Meteo rss stuff
    DOM_LANG_TO_METEO = {
        'en': 'English',
        'de': 'German',
        'se': 'Swedish',
        'fr': 'French',
        'es': 'Spanish',
        'fi': 'Finnish'
    }

    # (fixed in 1.6.3: language name -> AWT_TRANSLATION column index. The
    # old getLangIndex() checked `if 'svenska' in meteoLang` / `'deutsch' in
    # meteoLang`, but meteoLang is always the *English* language name from
    # DOM_LANG_TO_METEO ('German', 'Swedish', ...) - those substrings can
    # never match, so German and Swedish detail-language selection always
    # silently fell back to English. This matches on the actual values used.)
    LANG_NAME_TO_INDEX = {
        'english': 0,
        'german': 1,
        'swedish': 2,
        'french': 3,
        'spanish': 4,
        'finnish': 5,
    }

    # meteoalarm's 4-colour awareness scale, taken from the entry <title>
    # (e.g. "Yellow Thunderstorm Warning issued for ..."), matching the old
    # plugin's wflag-l1..l4 icon-derived level scale (1=green/none .. 4=red)
    COLOR_TO_LEVEL = {'green': 1, 'yellow': 2, 'orange': 3, 'red': 4}
    # fallback if the title didn't parse - CAP's own severity vocabulary
    SEVERITY_TO_LEVEL = {'minor': 2, 'moderate': 3, 'severe': 4, 'extreme': 4}

    TITLE_PATTERN = re.compile(
        r'^(?P<color>\w+)\s+(?P<type>.+?)\s+Warning issued for', re.IGNORECASE)

    def __init__(self, rssUrl="https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-germany", rssCode="202", domLangSetting="de", detailSetting="detail_dom_lang",
                 iconSetting="icon_inline_detail", locationName=""):
        self.rssCode = rssCode
        self.rssUrl = rssUrl
        self.locationName = locationName
        self.lastUpdate = datetime.now()
        self.debug = False
        self.error = False
        self.nextpoll = datetime.now()
        self.detailNo = True
        self.detailLang = "English"
        self.iconNo = True

        self.iconType = ''
        self.langKey = 0  # 0=en,1=de,2=se,3=fr,4=es,5=fi
        self._lastRawData = None
        self.configure(domLangSetting, detailSetting, iconSetting)
        self.reset()
        return

    def getDayTitle(self, idx):
        '''returns the title or name for the device.
        "Today: {location} ({update time from rss})"
        Arguments:
            idx {int} -- 0 for today, 1 for tomorrow

        Returns:
            str -- the name: like "Today: {location} ({update time from rss})"
        '''
        s = ''
        if self.hasError is True:
            s = getAwtTranslation(idx, self.langKey) + ': ERROR!!!'
        else:
            # (fixed in 1.6.1/refined in 1.6.3: pubDate can legitimately be
            # None when the whole feed currently has zero entries anywhere -
            # e.g. a quiet day with no warnings at all. That's a normal,
            # good state, not an error - so we just omit the timestamp
            # instead of crashing on mktime(None) or mislabeling it ERROR.)
            loc = self.location if self.location is not None else self.locationName
            s = getAwtTranslation(idx, self.langKey) + ': ' + loc
            if Meteo.SHOW_DATE_IN_NAME is True and self.pubDate is not None:
                dt = datetime.fromtimestamp(mktime(self.pubDate))
                s = "{} ({:%H:%M})".format(s, dt)
        return s

    def getTodayTitle(self):
        return self.getDayTitle(200)

    def getTomorrowTitle(self):
        return self.getDayTitle(201)

    def configure(self, domLangSetting, detailSetting, iconSetting):
        '''does the configuration of this service

        Arguments:
            domLangSetting {str} -- the settings from domoticz
            detailSetting {str} -- configuration of detail/verbosity + language
            iconSetting {str} -- kept for backward compatibility with existing
                                  hardware configs; the CAP feed no longer
                                  provides per-warning icon images, so this
                                  no longer has any visual effect
        '''

        # check details and language
        if detailSetting == 'no_detail' or len(detailSetting) <= 0:
            self.detailNo = True
            Domoticz.Debug("switched details off for status text (compact mode).")
            self.detailLang = getMeteoLang(domLangSetting)
            self.langKey = getLangIndex(self.detailLang)
        else:
            self.detailNo = False
            Domoticz.Debug(
                "1#Detail turned on. Fallback-Language is: " + self.detailLang)
            if 'detail_dom_lang' in detailSetting:
                Domoticz.Debug("1.2#Try translate lang from domoticz settings (='{}') to meteo rss conform"
                               .format(domLangSetting))
                self.detailLang = getMeteoLang(domLangSetting)
                self.langKey = getLangIndex(self.detailLang)
            else:
                self.detailLang = detailSetting
                self.langKey = getLangIndex(self.detailLang)

            Domoticz.Debug("2#Detail turned on. Language is: '{}'"
                           .format(self.detailLang))
            Domoticz.Debug("settings lang: {}, detail lang: {} key: {}"
                           .format(domLangSetting, self.detailLang,
                                   self.langKey))

        # check icon
        if iconSetting == 'icon_no' or len(iconSetting) <= 0:
            self.iconNo = True
        else:
            self.iconNo = False
            self.iconType = iconSetting
            # (changed in 1.6.3: the CAP feed provides no per-warning icon
            # images at all, unlike the old RSS/HTML format - this setting
            # is kept only so existing hardware configs don't break, but it
            # no longer changes anything visually.)
            Domoticz.Debug(
                "Icon setting '{}' requested, but the current MeteoAlarm "
                "Atom/CAP feed does not provide per-warning icon images - "
                "this setting has no visual effect.".format(iconSetting))

    def dumpMeteoConfig(self):
        '''just print configuration and settings to log
        '''

        Domoticz.Log(
            "detailNo: {}\ndetailLang: {}\n"
            "langKey: {}\niconNo: {}\niconType:{}"
            .format(
                self.detailNo,
                self.detailLang,
                self.langKey,
                self.iconNo,
                self.iconType
            )
        )

    def reset(self):
        '''set all important fields to None
        '''

        self.location = None
        self.todayDetail = None
        self.todayLevel = None
        self.tomorrowDetail = None
        self.tomorrowLevel = None
        self.observationDate = None
        self.pubDate = None
        self.needUpdate = True
        self.resetError()

    def setError(self, error):
        '''sets the error msg and put error flag to True

        Arguments:
            error {Exception} -- the caught exception
        '''
        self.hasError = True
        self.errorMsg = error

    def resetError(self):
        '''just removes error flag and deletes last error msg
        '''
        self.hasError = False
        self.errorMsg = None

    def dumpMeteoStatus(self):
        '''just print current status to log
        '''

        Domoticz.Log(
            "##########################################\n"
            "{} ({}) :\nHeute:\t{}-{}\n\rMorgen:\t{}-{}\nneed update?:\t{}"
            "\nError?: {}\tErrorMsg: {}"
            .format(
                self.location,
                self.pubDate,
                self.todayLevel,
                self.todayDetail,
                self.tomorrowLevel,
                self.tomorrowDetail,
                self.needUpdate,
                self.hasError,
                self.errorMsg
            )
        )

    def _extractGeocode(self, entry):
        '''pull the EMMA_ID region code out of an entry.

        Primary source is the geocode link href
        (...?geocode=EMMA_ID:LU001), which is explicit and stable.
        Falls back to feedparser's flattened <cap:geocode><value>
        element, which lands directly on the entry as `.value` since
        feedparser flattens unknown-namespace child elements.

        Arguments:
            entry {feedparser entry}

        Returns:
            str | None -- the EMMA_ID code, e.g. 'LU001'
        '''
        for l in entry.get('links', []):
            href = l.get('href', '') or ''
            m = re.search(r'geocode=EMMA_ID:([A-Za-z0-9]+)', href)
            if m:
                return m.group(1)
        return entry.get('value')

    def _classifyEntry(self, entry):
        '''derive (level, awt-translation-key, human type text) for one
        matched CAP entry, from its <title> (e.g. "Yellow Thunderstorm
        Warning issued for Luxembourg - Canton X") with a cap:severity
        fallback if the title doesn't parse as expected.

        Arguments:
            entry {feedparser entry}

        Returns:
            (int, int|None, str) -- (level 1-4, AWT_TRANSLATION key or
            None if unrecognized, the raw type text from the title)
        '''
        title = str(getattr(entry, 'title', ''))
        m = Meteo.TITLE_PATTERN.match(title)
        typeText = m.group('type').strip() if m else str(getattr(entry, 'cap_event', 'Warning'))
        color = m.group('color').lower() if m else ''
        level = Meteo.COLOR_TO_LEVEL.get(color, 0)
        if level == 0:
            sev = str(getattr(entry, 'cap_severity', '')).lower()
            level = Meteo.SEVERITY_TO_LEVEL.get(sev, 2)

        normType = re.sub(r'[^a-z]', '', typeText.lower())
        if 'rain' in normType and 'flood' in normType:
            awtKey = 12
        elif 'flood' in normType:
            awtKey = 11
        elif 'rain' in normType:
            awtKey = 10
        elif 'thunderstorm' in normType:
            awtKey = 3
        elif 'wind' in normType:
            awtKey = 1
        elif 'snow' in normType or 'ice' in normType:
            awtKey = 2
        elif 'fog' in normType:
            awtKey = 4
        elif 'hightemperature' in normType:
            awtKey = 5
        elif 'lowtemperature' in normType:
            awtKey = 6
        elif 'coastal' in normType:
            awtKey = 7
        elif 'forestfire' in normType or 'fire' in normType:
            awtKey = 8
        elif 'avalanche' in normType:
            awtKey = 9
        else:
            awtKey = None

        return level, awtKey, typeText

    def _summarizeDay(self, entries, idx):
        '''build the device text + highest level for one day (today=0,
        tomorrow=1) from the CAP entries relevant to that day.

        Arguments:
            entries {list} -- matched feedparser entries active on that day
            idx {int} -- 0 for today, 1 for tomorrow (used for the
                         multi-day date/offset formatting)

        Returns:
            (str, int) -- (device text, highest level)
        '''
        if not entries:
            d = getAwtTranslation(99, self.langKey)
            return d, 1

        relevantDate = datetime.now().astimezone() + timedelta(days=idx)
        parts = []
        highestLevel = 0
        for entry in entries:
            level, awtKey, typeText = self._classifyEntry(entry)
            if level > highestLevel:
                highestLevel = level
            label = getAwtTranslation(awtKey, self.langKey) if awtKey is not None else typeText

            if self.detailNo:
                parts.append("{} ({})".format(label, level))
                continue

            area = str(getattr(entry, 'cap_areadesc', '')) or self.locationName
            onset = parseCapIsoDate(getattr(entry, 'cap_onset', None)) \
                or parseCapIsoDate(getattr(entry, 'cap_effective', None))
            expires = parseCapIsoDate(getattr(entry, 'cap_expires', None))
            timeTxt = ''
            if onset is not None and expires is not None:
                # (multi-day span handling, per the original TODO: "sometimes
                # until goes for a few days... clock is not enough" - now
                # driven by the real onset/expires timestamps instead of a
                # regex-scraped "From: ... Until: ..." text block)
                startTxt = getSDatesFromDate(onset, relevantDate)[0]
                endTxt = getSDatesFromDate(expires, relevantDate)[0]
                timeTxt = " {}-{}".format(startTxt, endTxt)
            parts.append("{} ({}) {}{}".format(label, level, area, timeTxt))

        text = "; ".join(parts)
        if len(text) > Meteo.MAX_SHOWN_DETAIL_LENGTH:
            text = text[:Meteo.MAX_SHOWN_DETAIL_LENGTH].rstrip() + "..."
        return text, highestLevel

    def _processFeed(self, feed):
        '''parse an already-fetched feedparser result and update
        location/pubDate/today/tomorrow state. Split out from
        readMeteoWarning() so it can be exercised directly against a
        saved feed sample for testing, independent of the network fetch.

        Arguments:
            feed {feedparser result}
        '''
        firstPubDate = None
        matchedEntries = []

        for key in feed["entries"]:
            if firstPubDate is None:
                firstPubDate = key.get('published_parsed')
            code = self._extractGeocode(key)
            if code != self.rssCode:
                continue
            matchedEntries.append(key)

        if not matchedEntries:
            Domoticz.Log("no entry found --> no alert")
            d = getAwtTranslation(99, self.langKey)
            newPubDate = firstPubDate
            self.needUpdate = (self.pubDate != newPubDate) or (self.todayLevel != 1)
            self.pubDate = newPubDate
            self.todayDetail = d
            self.todayLevel = 1
            self.tomorrowDetail = d
            self.tomorrowLevel = 1
            return

        dated = [e for e in matchedEntries if e.get('published_parsed')]
        newestEntry = max(dated, key=lambda e: e.get('published_parsed')) if dated else matchedEntries[0]
        newPubDate = newestEntry.get('published_parsed')
        newLocation = str(getattr(newestEntry, 'cap_areadesc', '')) or self.locationName

        self.needUpdate = (self.pubDate != newPubDate)
        self.pubDate = newPubDate
        self.location = newLocation

        now = datetime.now().astimezone()
        today = now.date()
        tomorrow = (now + timedelta(days=1)).date()

        todayEntries = []
        tomorrowEntries = []
        for entry in matchedEntries:
            onset = parseCapIsoDate(getattr(entry, 'cap_onset', None)) \
                or parseCapIsoDate(getattr(entry, 'cap_effective', None)) or now
            expires = parseCapIsoDate(getattr(entry, 'cap_expires', None)) or onset
            onsetDate = onset.date()
            expiresDate = expires.date()
            if onsetDate <= today <= expiresDate:
                todayEntries.append(entry)
            if onsetDate <= tomorrow <= expiresDate:
                tomorrowEntries.append(entry)

        self.todayDetail, self.todayLevel = self._summarizeDay(todayEntries, 0)
        self.tomorrowDetail, self.tomorrowLevel = self._summarizeDay(tomorrowEntries, 1)

    def readMeteoWarning(self):
        """tries to get rss data from Meteo and parse it.
        Values are stored on attributes.
        check self.needUpdate. if we get new data we set a flag there.

        """

        self._lastRawData = None

        try:
            Domoticz.Debug('Retrieve meteo weather data from ' + self.rssUrl)

            # fetch manually with an explicit timeout instead of letting
            # feedparser.parse() do its own unbounded fetch - previously a
            # hung/slow connection here would block the entire Domoticz
            # heartbeat cycle indefinitely.
            try:
                req = urllib.request.Request(
                    self.rssUrl,
                    headers={'User-Agent': 'Domoticz-MeteoAlarmEU-Atom/1.6.3'})
                response = urllib.request.urlopen(
                    req, timeout=Meteo.FEED_FETCH_TIMEOUT_SECONDS)
                httpStatus = response.getcode()
                self._lastRawData = response.read()
            except socket.timeout:
                raise Exception("timed out after {}s fetching feed"
                                .format(Meteo.FEED_FETCH_TIMEOUT_SECONDS))
            except urllib.error.HTTPError as e:
                raise Exception("HTTP error {} fetching feed".format(e.code))
            except urllib.error.URLError as e:
                raise Exception("could not reach feed: {}"
                                .format(getattr(e, 'reason', e)))

            if httpStatus != 200:
                raise Exception("did not find feed for {} (HTTP {})"
                                .format(self.rssUrl, httpStatus))

            feed = feedparser.parse(self._lastRawData)

            if getattr(feed, 'bozo', 0):
                Domoticz.Debug("Feed parsed with warnings (bozo): {}"
                               .format(getattr(feed, 'bozo_exception', 'unknown')))

            self._processFeed(feed)
            self.lastUpdate = datetime.now()

        except (Exception) as e:
            Domoticz.Error("Error: " + str(e) + " URL: " + self.rssUrl)
            if self._lastRawData is not None:
                preview = self._lastRawData[:500]
                Domoticz.Debug(
                    "Raw feed response (first 500 bytes) for diagnosis: {}"
                    .format(preview))
            self.setError(e)
            return


#############################################################################
#                       Data specific functions                             #
#############################################################################


def getMeteoLang(domLanguage):
    """translate the domoticz language from Settings["Language"] to meteo confrom.
    eg: Domoticz: de -> meteo: German (the AWT_TRANSLATION column name).

    Arguments:
        domLanguage {str} -- value from domoticz settings for language

    Returns:
        str -- the matching language name used to pick an AWT_TRANSLATION column
    """

    if domLanguage in Meteo.DOM_LANG_TO_METEO:
        mLang = Meteo.DOM_LANG_TO_METEO[domLanguage]
    else:
        Domoticz.Error(
            "Given key '{}' does not exist in Mapping from Domoticz to Meteo! Falling back to English."
            .format(domLanguage))
        mLang = "English"
    return mLang


def getLangIndex(meteoLang):
    """takes the language name from getMeteoLang()/detailSetting and maps
    it to the matching AWT_TRANSLATION column index. Falls back to English
    (0) for anything unrecognized.

    Arguments:
        meteoLang {str} -- language name, e.g. 'German', 'Swedish'

    Returns:
        int -- AWT_TRANSLATION column index, 0-5
    """

    return Meteo.LANG_NAME_TO_INDEX.get(str(meteoLang).strip().lower(), 0)


def getAwtTranslation(idx, langIndex):
    """
    takes the key from meteo and looks for defined translation

    Arguments:
        idx {[type]} -- key/index from meteo rss awt, but its extended, so 99 works as well
        langIndex {int} -- index into the AWT_TRANSLATION language columns (0-5)

    Returns:
        str -- translated longform for given awt key
    """

    txt = str(idx)
    if int(idx) in Meteo.AWT_TRANSLATION:
        t = Meteo.AWT_TRANSLATION[int(idx)]
        txt = t[langIndex] if 0 <= langIndex < len(t) else t[0]
    else:
        txt = idx
        Domoticz.Error(
            "BLZ: did not found key '{}' in translation list!".format(idx))
    return txt


def getSDatesFromDate(date, relevantDate):
    '''format a datetime relative to relevantDate (today's or tomorrow's
    device date). If it falls on the same calendar day as relevantDate,
    just the time is shown; otherwise the date, time, and a day-offset are
    shown too - this is what actually implements the "sometimes until goes
    for a few days... clock is not enough" TODO, now driven by real
    cap:onset/cap:expires timestamps instead of regex-scraped RSS text.

    Arguments:
        date {datetime} -- a timezone-aware or naive datetime (from
                            parseCapIsoDate)
        relevantDate {datetime} -- the day being rendered (today or
                                    tomorrow, as a datetime)

    Returns:
        [array] -- [shortDate, longDate]
    '''
    longDate = "{}.{}. {:02d}:{:02d}".format(date.day, date.month, date.hour, date.minute)
    dayDelta = (date.date() - relevantDate.date()).days
    if dayDelta == 0:
        shortDate = "{:02d}:{:02d}".format(date.hour, date.minute)
    else:
        shortDate = "{}.{}. {:02d}:{:02d} ({:+d}d)".format(
            date.day, date.month, date.hour, date.minute, dayDelta)
    result = [shortDate, longDate]
    return result
