# moved logic of Meteo rss warning to extra class
#
# Parses meteoalarm.org's CAP-Atom feed directly (cap:event, cap:severity,
# cap:onset, cap:expires, cap:status, cap:urgency) - see plugin.py's
# docstring for the full version history; this file follows the same
# version number.
import re
from calendar import timegm
from datetime import datetime, timedelta

import feedparser
import urllib.request
import urllib.error
import socket

try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz

PLUGIN_VERSION = "1.7.3"

# used only for early sanity-check warnings, never to reject a URL: a
# non-matching URL is still used exactly as configured
EXPECTED_FEED_HOST = "feeds.meteoalarm.org"
EXPECTED_FEED_PATH_HINT = "atom"

# MeteoAlarm EMMA_ID region codes are two letters followed by digits
# (e.g. LU001). The check is deliberately lenient - a code that does not
# match only produces a warning, so an unusual but valid code is never
# refused. The classic mistake it catches is a leftover numeric RSS-era
# code such as "202".
REGION_CODE_SHAPE = re.compile(r'^[A-Z]{2}[A-Z0-9]+$')

# Country slug of a '...legacy-atom-<slug>' feed URL -> EMMA_ID prefix.
# Best effort: a slug missing from this table simply skips the
# country/code mismatch warning.
FEED_SLUG_TO_PREFIX = {
    'austria': 'AT', 'belgium': 'BE', 'bulgaria': 'BG', 'croatia': 'HR',
    'cyprus': 'CY', 'czechia': 'CZ', 'denmark': 'DK', 'estonia': 'EE',
    'finland': 'FI', 'france': 'FR', 'germany': 'DE', 'greece': 'GR',
    'hungary': 'HU', 'iceland': 'IS', 'ireland': 'IE', 'italy': 'IT',
    'latvia': 'LV', 'lithuania': 'LT', 'luxembourg': 'LU', 'malta': 'MT',
    'netherlands': 'NL', 'norway': 'NO', 'poland': 'PL', 'portugal': 'PT',
    'romania': 'RO', 'slovakia': 'SK', 'slovenia': 'SI', 'spain': 'ES',
    'sweden': 'SE', 'switzerland': 'CH',
}


def parseRegionCodes(raw):
    """split the Mode2 setting into a clean list of region codes:
    separated by commas, semicolons or whitespace, upper-cased, with
    duplicates removed (first occurrence wins, so the primary region keeps
    Units 1/2).

    Arguments:
        raw {str} -- e.g. "LU002, lu001;LU002"

    Returns:
        list[str] -- e.g. ['LU002', 'LU001']
    """
    codes = []
    for token in re.split(r'[,;\s]+', str(raw or '').upper()):
        if token and token not in codes:
            codes.append(token)
    return codes


def feedCountryPrefix(url):
    """EMMA_ID country prefix for a '...legacy-atom-<country>' URL, or None
    when the URL has another shape or the country is not in the table."""
    m = re.search(r'atom-([a-z0-9-]+?)/?$', str(url or '').strip().lower().split('?')[0])
    return FEED_SLUG_TO_PREFIX.get(m.group(1)) if m else None


def validateConfig(url, rawCodes):
    """check the hardware settings once, at start-up.

    A configuration *error* means polling cannot possibly work (empty or
    non-http(s) URL, no region code) - the plugin then reports it once and
    does not poll at all, instead of retrying a request that can never
    succeed. A *warning* is only a hint (URL or region code looks unusual);
    the setting is still used as configured.

    Returns:
        (errors, warnings, codes) -- two lists of messages and the parsed
        region code list
    """
    errors = []
    warnings = []
    url = str(url or '').strip()
    codes = parseRegionCodes(rawCodes)

    if not url:
        errors.append("RSSFeed (Mode1) is empty - enter your country's Atom feed URL")
    elif not re.match(r'^https?://', url, re.IGNORECASE):
        errors.append("RSSFeed (Mode1) '{}' is not an http(s) URL".format(url))
    else:
        if EXPECTED_FEED_HOST not in url:
            warnings.append("Configured RSSFeed URL '{}' does not look like a {} URL"
                            .format(url, EXPECTED_FEED_HOST))
        elif EXPECTED_FEED_PATH_HINT not in url.lower():
            warnings.append("Configured RSSFeed URL '{}' does not look like an Atom feed - legacy RSS "
                            "feeds were sunset; use a '...legacy-atom-<country>' URL".format(url))

    if not codes:
        errors.append("RSSCode(s) (Mode2) is empty - enter at least one region code such as LU001")

    prefix = feedCountryPrefix(url)
    for code in codes:
        if not REGION_CODE_SHAPE.match(code):
            warnings.append("Region code '{}' does not look like a MeteoAlarm EMMA_ID (two letters followed "
                            "by digits, e.g. LU001) - it will probably never match a warning".format(code))
        elif prefix and not code.startswith(prefix):
            warnings.append("Region code '{}' does not start with '{}', the country prefix of this feed - "
                            "it will probably never match a warning".format(code, prefix))
    return errors, warnings, codes


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


def fetchFeed(url, timeoutSeconds, userAgent="Domoticz-MeteoAlarmEU-Atom/{}".format(PLUGIN_VERSION)):
    """fetch and parse a feed URL once. Module-level (not tied to a single
    Meteo instance) so multiple regions configured against the same feed
    can share one HTTP fetch per heartbeat instead of each doing their own.

    Arguments:
        url {str}
        timeoutSeconds {int}
        userAgent {str}

    Returns:
        (feedparser result, bytes) -- the parsed feed and the raw response
                                        body (kept for debug/error dumps)

    Raises:
        Exception -- on timeout, HTTP error, connection error, or non-200
                     status. Always a plain Exception with a clear message,
                     never the raw urllib/socket exception type, so callers
                     have one type to catch.
    """
    try:
        req = urllib.request.Request(url, headers={'User-Agent': userAgent})
        response = urllib.request.urlopen(req, timeout=timeoutSeconds)
        httpStatus = response.getcode()
        rawData = response.read()
    except socket.timeout:
        raise Exception("timed out after {}s fetching feed".format(timeoutSeconds))
    except urllib.error.HTTPError as e:
        raise Exception("HTTP error {} fetching feed".format(e.code))
    except urllib.error.URLError as e:
        raise Exception("could not reach feed: {}".format(getattr(e, 'reason', e)))

    if httpStatus != 200:
        raise Exception("did not find feed for {} (HTTP {})".format(url, httpStatus))

    feed = feedparser.parse(rawData)
    if getattr(feed, 'bozo', 0):
        Domoticz.Debug("Feed parsed with warnings (bozo): {}"
                       .format(getattr(feed, 'bozo_exception', 'unknown')))

    # (added in 1.7.2) feedparser never raises on bad input. A captive-portal
    # or error page served with HTTP 200 parses into a result with no
    # entries, which would otherwise be read as "no warnings" (a false
    # all-clear). feedparser reports the detected format in `version`
    # ('atom10' for a real Atom feed - also one with zero active warnings,
    # '' for HTML, JSON, plain text and other non-feeds). To make sure a
    # real feed can never be refused, BOTH signals must be missing: no
    # recognised format AND no feed-level title/id/updated element.
    if (not feed.get('entries') and not feed.get('version')
            and not any(key in feed.get('feed', {}) for key in ('title', 'id', 'updated'))):
        raise Exception("response is not a valid Atom feed ({} bytes received, first bytes: {!r})"
                        .format(len(rawData), rawData[:60]))
    return feed, rawData


class Meteo:
    # ####################################
    # Common definitions
    MAX_SHOWN_DETAIL_LENGTH = 200
    SHOW_DATE_IN_NAME = True
    FEED_FETCH_TIMEOUT_SECONDS = 15

    AWT_TRANSLATION = {
        # idx: [English, German, Swedish, French, Spanish, Finnish, Luxembourgish]
        1: ["Wind", "Wind", "Wind", "Vent", "Viento", "Tuuli", "Wand"],
        2: ["Snow/Ice", "Schnee/Eis", "Snö/Is", "Neige/Verglas", "Nieve/Hielo", "Lumi/Jää", "Schnéi/Äis"],
        3: ["ThunderStorm", "Gewitter", "Åska", "Orage", "Tormenta", "Ukkonen", "Donnerwieder"],
        4: ["Fog", "Nebel", "Dimma", "Brouillard", "Niebla", "Sumu", "Niwel"],
        5: ["High Temp", "Hohe Temp.", "Hög temp.", "Températures élevées", "Temperatura alta", "Korkea lämpötila", "Héich Temperaturen"],
        6: ["Low Temp", "Niedrige Temp.", "Låg temp.", "Températures basses", "Temperatura baja", "Matala lämpötila", "Niddreg Temperaturen"],
        7: ["Coastal Event", "Küstenereignis", "Kusthändelse", "Phénomène côtier", "Fenómeno costero", "Rannikkoilmiö", "Küstenevenement"],
        8: ["Forestfire", "Waldbrand", "Skogsbrand", "Feu de forêt", "Incendio forestal", "Metsäpalo", "Bëschbrand"],
        9: ["Avalanches", "Lawinen", "Laviner", "Avalanches", "Avalanchas", "Lumivyöryt", "Avalangen"],
        10: ["Rain", "Regen", "Regn", "Pluie", "Lluvia", "Sade", "Reen"],
        11: ["Flood", "Flut", "Översvämning", "Inondation", "Inundación", "Tulva", "Iwwerschwemmung"],
        12: ["Rain-Flood", "Regen-Flut", "Regn-Översvämning", "Pluie-Inondation", "Lluvia-Inundación", "Sade-Tulva", "Reen-Iwwerschwemmung"],
        99: ["No special awareness required", "Allet knorke!", "Ingen särskild uppmärksamhet krävs",
             "Aucune vigilance particulière requise", "No se requiere atención especial",
             "Ei erityistä varautumista vaadita", "Keng speziell Opmierksamkeet néideg"],
        200: ["Today", "Heute", "Idag", "Aujourd'hui", "Hoy", "Tänään", "Haut"],
        201: ["Tomorrow", "Morgen", "Imorgon", "Demain", "Mañana", "Huomenna", "Muer"]
    }

    # (fixed in 1.7.0: Domoticz's actual language code for Swedish is 'sv'
    # - 'se' is not a real Domoticz language code and never matched
    # anything, silently making Swedish behave the same as an unmapped
    # language. Verified against Domoticz's own ecosystem conventions -
    # e.g. Dashticz's config uses 'sv_SE' - since a live Domoticz instance
    # wasn't available to check Settings["Language"] directly.)
    #
    # Luxembourgish ('lb') is intentionally NOT mapped here: Domoticz's
    # built-in UI languages don't appear to include Luxembourgish, so
    # auto-detecting it from Settings["Language"] would never trigger.
    # It's offered instead as an explicit Mode5 choice ("Luxembourgish"),
    # same as the other non-auto-detected options.
    DOM_LANG_TO_METEO = {
        'en': 'English',
        'de': 'German',
        'sv': 'Swedish',
        'fr': 'French',
        'es': 'Spanish',
        'fi': 'Finnish'
    }

    LANG_NAME_TO_INDEX = {
        'english': 0,
        'german': 1,
        'swedish': 2,
        'french': 3,
        'spanish': 4,
        'finnish': 5,
        'luxembourgish': 6,
    }

    COLOR_TO_LEVEL = {'green': 1, 'yellow': 2, 'orange': 3, 'red': 4}
    SEVERITY_TO_LEVEL = {'minor': 2, 'moderate': 3, 'severe': 4, 'extreme': 4}

    TITLE_PATTERN = re.compile(
        r'^(?P<color>\w+)\s+(?P<type>.+?)\s+Warning issued for', re.IGNORECASE)

    # AWT key -> base name used for the custom severity/type icon set
    # (see meteoalarm_icons.zip / icons.txt). Kept separate from
    # AWT_TRANSLATION since icon names are not language-dependent.
    ICON_NAME_BY_AWT = {
        1: "Wind", 2: "SnowIce", 3: "Thunderstorm", 4: "Fog", 5: "Hightemp",
        6: "Lowtemp", 7: "Coastal", 8: "Forestfire", 9: "Avalanche",
        10: "Rain", 11: "Flood", 12: "Rainflood",
    }
    # must match the filename prefix used when packaging meteoalarm_icons.zip
    ICON_FILE_PREFIX = "MeteoAlarmEUAtom"

    # only these cap:status values represent a real, currently-valid
    # warning - Test/Exercise/Draft/System entries are excluded
    VALID_CAP_STATUSES = {'actual'}

    def __init__(self, rssUrl="https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-germany", rssCode="202", domLangSetting="de", detailSetting="detail_dom_lang",
                 iconSetting="icon_inline_detail", locationName=""):
        self.rssCode = rssCode
        self.rssUrl = rssUrl
        self.locationName = locationName
        self.lastUpdate = datetime.now()
        self.detailNo = True
        self.detailLang = "English"
        self.iconNo = True

        self.iconType = ''
        self.langKey = 0  # 0=en,1=de,2=sv,3=fr,4=es,5=fi,6=lb
        self._lastRawData = None
        self.configure(domLangSetting, detailSetting, iconSetting)
        self.reset()
        return

    def getDayTitle(self, idx):
        '''returns the title or name for the device.
        "Today: {location} ({update time from rss})"
        '''
        s = ''
        if self.hasError is True:
            s = getAwtTranslation(idx, self.langKey) + ': ERROR!!!'
        else:
            loc = self.location if self.location is not None else self.locationName
            s = getAwtTranslation(idx, self.langKey) + ': ' + loc
            if Meteo.SHOW_DATE_IN_NAME is True and self.pubDate is not None:
                # (fixed in 1.7.2: feedparser's *_parsed values are UTC, and
                # time.mktime() reads them as local time, so the shown time
                # was off by the UTC offset. calendar.timegm() is correct.)
                dt = datetime.fromtimestamp(timegm(self.pubDate))
                s = "{} ({:%H:%M})".format(s, dt)
        return s

    @staticmethod
    def _publishedStamp(entries):
        '''"HH:MM" - or "D.M. HH:MM" when not published today - of the newest
        publish time among the given entries, in local time. None if no
        entry carries one. Shown at the end of the device text since 1.7.2,
        replacing the publish time that used to be part of the device name.
        '''
        stamps = [e.get('published_parsed') for e in entries if e.get('published_parsed')]
        if not stamps:
            return None
        published = datetime.fromtimestamp(timegm(max(stamps)))
        if published.date() == datetime.now().date():
            return "{:%H:%M}".format(published)
        return "{:%d.%m. %H:%M}".format(published)

    def getTodayTitle(self):
        return self.getDayTitle(200)

    def getTomorrowTitle(self):
        return self.getDayTitle(201)

    def getDayIconKey(self, idx):
        '''returns the custom icon name (e.g. "MeteoAlarmEUAtomThunderstormL3")
        for this day's worst warning, or None if there's no specific
        category to show, no active warning, or icons are switched off
        (Mode6 = NO_ICON) - callers should treat None as "use the default
        Alert icon", never as an error.

        Arguments:
            idx {int} -- 0 for today, 1 for tomorrow
        '''
        # (fixed: this previously ignored self.iconNo entirely, so
        # selecting "NO_ICON" in Mode6 had no effect as long as the icon
        # zip loaded successfully - the only gate was the plugin-level
        # iconsLoaded flag, not the user's actual setting.)
        if self.iconNo:
            return None
        awtKey = self.todayIconAwt if idx == 0 else self.tomorrowIconAwt
        level = self.todayLevel if idx == 0 else self.tomorrowLevel
        if awtKey is None or awtKey not in Meteo.ICON_NAME_BY_AWT or not level or level < 1:
            return None
        return "{}{}L{}".format(Meteo.ICON_FILE_PREFIX, Meteo.ICON_NAME_BY_AWT[awtKey], int(level))

    def configure(self, domLangSetting, detailSetting, iconSetting):
        '''does the configuration of this service'''
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
                           .format(domLangSetting, self.detailLang, self.langKey))

        if iconSetting == 'icon_no' or len(iconSetting) <= 0:
            self.iconNo = True
        else:
            self.iconNo = False
            self.iconType = iconSetting
            Domoticz.Debug(
                "Icon setting '{}' requested - as of 1.7.0 this enables the "
                "plugin's own bundled severity/type icon set (the feed "
                "itself no longer provides icons).".format(iconSetting))

    def dumpMeteoConfig(self):
        Domoticz.Log(
            "detailNo: {}\ndetailLang: {}\n"
            "langKey: {}\niconNo: {}\niconType:{}"
            .format(self.detailNo, self.detailLang, self.langKey, self.iconNo, self.iconType)
        )

    def reset(self):
        '''set all important fields to None'''
        self.location = None
        self.todayDetail = None
        self.todayLevel = None
        self.todayIconAwt = None
        self.tomorrowDetail = None
        self.tomorrowLevel = None
        self.tomorrowIconAwt = None
        self.pubDate = None
        self.needUpdate = True
        self.resetError()

    def setError(self, error):
        self.hasError = True
        self.errorMsg = error

    def resetError(self):
        self.hasError = False
        self.errorMsg = None

    def dumpMeteoStatus(self):
        Domoticz.Log(
            "##########################################\n"
            "{} ({}) :\nHeute:\t{}-{}\n\rMorgen:\t{}-{}\nneed update?:\t{}"
            "\nError?: {}\tErrorMsg: {}"
            .format(self.location, self.pubDate, self.todayLevel, self.todayDetail,
                    self.tomorrowLevel, self.tomorrowDetail, self.needUpdate,
                    self.hasError, self.errorMsg)
        )

    def _extractGeocode(self, entry):
        '''pull the EMMA_ID region code out of an entry - primary source is
        the geocode link href (explicit/stable), falling back to
        feedparser's flattened cap:geocode value.'''
        for link in entry.get('links', []):
            href = link.get('href', '') or ''
            m = re.search(r'geocode=EMMA_ID:([A-Za-z0-9]+)', href)
            if m:
                return m.group(1)
        return entry.get('value')

    def _classifyEntry(self, entry):
        '''derive (level, awt-translation-key, human type text) for one
        matched CAP entry, from its <title> with a cap:severity fallback.
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
        '''build the device text, highest level, and worst-entry AWT key
        (for icon lookup) for one day (today=0, tomorrow=1).

        Returns:
            (str, int, int|None) -- (device text, highest level, AWT key
            of the entry that drove the highest level)
        '''
        if not entries:
            d = getAwtTranslation(99, self.langKey)
            return d, 1, None

        relevantDate = datetime.now().astimezone() + timedelta(days=idx)
        parts = []
        highestLevel = 0
        worstAwtKey = None
        for entry in entries:
            level, awtKey, typeText = self._classifyEntry(entry)
            if level > highestLevel:
                highestLevel = level
                worstAwtKey = awtKey
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
                startTxt = getSDatesFromDate(onset, relevantDate)[0]
                endTxt = getSDatesFromDate(expires, relevantDate)[0]
                timeTxt = " {}-{}".format(startTxt, endTxt)

            urgency = str(getattr(entry, 'cap_urgency', '') or '').strip().lower()
            urgencyTxt = ''
            if urgency == 'future':
                urgencyTxt = " [upcoming]"
            elif urgency == 'past':
                urgencyTxt = " [ending]"

            parts.append("{} ({}) {}{}{}".format(label, level, area, timeTxt, urgencyTxt))

        text = "; ".join(parts)
        if len(text) > Meteo.MAX_SHOWN_DETAIL_LENGTH:
            text = text[:Meteo.MAX_SHOWN_DETAIL_LENGTH].rstrip() + "..."
        # (1.7.2) publish time of the newest message for this day, appended
        # after truncation so it is never cut off
        stamp = Meteo._publishedStamp(entries)
        if stamp:
            text = "{} [{}]".format(text, stamp)
        return text, highestLevel, worstAwtKey

    def processFetchedFeed(self, feed):
        '''parse an already-fetched feedparser result and update this
        instance's location/pubDate/today/tomorrow state for its
        configured rssCode. Split out from readMeteoWarning() so a single
        shared fetch (see fetchFeed()) can be processed by several Meteo
        instances when monitoring multiple regions.

        Arguments:
            feed {feedparser result}
        '''
        try:
            prevFingerprint = (self.todayLevel, self.todayDetail,
                                self.tomorrowLevel, self.tomorrowDetail)
            self.resetError()

            firstPubDate = None
            matchedEntries = []
            skippedNonActual = 0

            for key in feed["entries"]:
                if firstPubDate is None:
                    firstPubDate = key.get('published_parsed')
                code = self._extractGeocode(key)
                if code != self.rssCode:
                    continue
                status = str(getattr(key, 'cap_status', '') or 'Actual').strip().lower()
                if status not in Meteo.VALID_CAP_STATUSES:
                    skippedNonActual += 1
                    continue
                matchedEntries.append(key)

            if skippedNonActual:
                Domoticz.Debug("Skipped {} non-Actual (Test/Exercise/Draft/System) "
                               "entries for code {}".format(skippedNonActual, self.rssCode))

            if not matchedEntries:
                Domoticz.Debug("no entry found for {} --> no alert".format(self.rssCode))
                d = getAwtTranslation(99, self.langKey)
                self.pubDate = firstPubDate
                self.todayDetail = d
                self.todayLevel = 1
                self.todayIconAwt = None
                self.tomorrowDetail = d
                self.tomorrowLevel = 1
                self.tomorrowIconAwt = None
            else:
                dated = [e for e in matchedEntries if e.get('published_parsed')]
                newestEntry = max(dated, key=lambda e: e.get('published_parsed')) if dated else matchedEntries[0]
                self.pubDate = newestEntry.get('published_parsed')
                self.location = str(getattr(newestEntry, 'cap_areadesc', '')) or self.locationName

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

                self.todayDetail, self.todayLevel, self.todayIconAwt = self._summarizeDay(todayEntries, 0)
                self.tomorrowDetail, self.tomorrowLevel, self.tomorrowIconAwt = self._summarizeDay(tomorrowEntries, 1)

            newFingerprint = (self.todayLevel, self.todayDetail,
                               self.tomorrowLevel, self.tomorrowDetail)
            self.needUpdate = (newFingerprint != prevFingerprint)
            self.lastUpdate = datetime.now()

        except Exception as e:
            Domoticz.Error("Error processing feed for region '{}': {}".format(self.rssCode, e))
            self.setError(e)

    def readMeteoWarning(self):
        """single-instance convenience wrapper: fetches the feed and
        processes it for this instance's region. For multi-region use,
        prefer calling the module-level fetchFeed() once and passing the
        result to processFetchedFeed() on each Meteo instance instead, to
        avoid redundant HTTP fetches of the same feed.
        """
        self._lastRawData = None
        try:
            Domoticz.Debug('Retrieve meteo weather data from ' + self.rssUrl)
            feed, rawData = fetchFeed(self.rssUrl, Meteo.FEED_FETCH_TIMEOUT_SECONDS)
            self._lastRawData = rawData
            self.processFetchedFeed(feed)
        except Exception as e:
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
    """translate the domoticz language code (Settings["Language"]) to the
    matching AWT_TRANSLATION column name.
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
    """maps a language name (e.g. 'German', 'Swedish') to its
    AWT_TRANSLATION column index. Falls back to English (0) for anything
    unrecognized.
    """
    return Meteo.LANG_NAME_TO_INDEX.get(str(meteoLang).strip().lower(), 0)


def getAwtTranslation(idx, langIndex):
    """looks up the translated label for an AWT key + language index."""
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
    device date), showing date + day-offset when it falls on a different
    calendar day - implements multi-day span display using real
    cap:onset/cap:expires timestamps.
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

