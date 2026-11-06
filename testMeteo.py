"""
testMeteo.py - test entry point for meteo.py, runnable outside Domoticz
via fakeDomoticz.py (per the pattern from ffes/domoticz-buienradar
referenced in the README).

Run with:
    python3 testMeteo.py

These tests build synthetic CAP-Atom feed XML with dates relative to a
FROZEN clock (today, 12:00 local time) instead of the real time of day.
Until 1.7.2 they used the real clock, which made them fail whenever they
ran within a few hours of midnight (a warning "ending in 1 hour" then
legitimately reaches tomorrow). Today's date is still real, so the data
never goes stale.
"""
import unittest
import tempfile
import os
import time
from datetime import datetime, timedelta, timezone

import feedparser
import meteo

_RealDatetime = datetime


class FrozenDatetime(_RealDatetime):
    """datetime whose now() is fixed, patched over meteo.datetime (and
    plugin.datetime in testPlugin.py) by freeze()."""
    _now = None  # an aware, local-time datetime

    @classmethod
    def now(cls, tz=None):
        base = cls._now
        if tz is None:
            return base.replace(tzinfo=None)
        return base.astimezone(tz)


def noon_today():
    return _RealDatetime.now().astimezone().replace(hour=12, minute=0, second=0, microsecond=0)


def clock_now():
    """the current (frozen if frozen) aware local time, for building test data"""
    return FrozenDatetime._now or _RealDatetime.now().astimezone()


def freeze(when, *modules):
    """freeze meteo (and any given extra modules) at `when`; returns a
    restore function suitable for addCleanup()."""
    FrozenDatetime._now = when
    patched = [(m, m.datetime) for m in (meteo,) + modules]
    for m, _ in patched:
        m.datetime = FrozenDatetime

    def restore():
        for m, original in patched:
            m.datetime = original
        FrozenDatetime._now = None
    return restore


class FrozenTestCase(unittest.TestCase):
    """every test in this module runs at 12:00 today (local time)"""

    def setUp(self):
        self.addCleanup(freeze(noon_today()))


def iso(dt):
    s = dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    return s[:-2] + ':' + s[-2:]


def utc_stamp(dt):
    """Atom timestamp in real UTC, as the live feed publishes them"""
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def build_feed(entries_xml):
    now = clock_now()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
  <id>tag:meteoalarm.org,test:LU</id><title>Test feed</title>
  <updated>{updated}</updated>
  {entries}
</feed>""".format(updated=utc_stamp(now), entries=entries_xml)
    fd, path = tempfile.mkstemp(suffix='.xml')
    with os.fdopen(fd, 'w') as f:
        f.write(xml)
    try:
        return feedparser.parse(path)
    finally:
        os.remove(path)


def make_entry(code, area, title, event, severity, onset_offset_hours,
                expires_offset_hours, urgency="Immediate", status="Actual",
                certainty="Likely", published_offset_hours=0):
    now = clock_now()
    onset = now + timedelta(hours=onset_offset_hours)
    published = now + timedelta(hours=published_offset_hours)
    expires = now + timedelta(hours=expires_offset_hours)
    return """
  <entry>
    <cap:geocode><valueName>EMMA_ID</valueName><value>{code}</value></cap:geocode>
    <link title="{area}" href="https://meteoalarm.org?geocode=EMMA_ID:{code}" hreflang="en"/>
    <cap:areaDesc>{area}</cap:areaDesc>
    <cap:event>{event}</cap:event>
    <cap:onset>{onset}</cap:onset>
    <cap:expires>{expires}</cap:expires>
    <cap:certainty>{certainty}</cap:certainty>
    <cap:severity>{severity}</cap:severity>
    <cap:urgency>{urgency}</cap:urgency>
    <cap:status>{status}</cap:status>
    <published>{pub}</published>
    <id>test-{code}-{event_id}</id>
    <title>{title}</title>
    <updated>{pub}</updated>
  </entry>""".format(code=code, area=area, title=title, event=event, severity=severity,
                      onset=iso(onset), expires=iso(expires), urgency=urgency,
                      status=status, certainty=certainty,
                      pub=utc_stamp(published), event_id=abs(hash(title)) % 10000)


def make_meteo(code, lang="en", detail="detail_dom_lang", location="Test Location"):
    return meteo.Meteo(rssUrl="dummy", rssCode=code, domLangSetting=lang,
                        detailSetting=detail, iconSetting="icon_inline_detail",
                        locationName=location)


class TestCapStatusFiltering(FrozenTestCase):
    def test_test_status_entries_are_excluded(self):
        entries = (
            make_entry("LU001", "Area", "Red Wind Warning issued for Luxembourg - Area",
                       "Severe wind warning", "Severe", -1, 3) +
            make_entry("LU001", "Area", "Red Flood Warning issued for Luxembourg - Area",
                       "Severe flood warning", "Extreme", -1, 3, status="Test")
        )
        feed = build_feed(entries)
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        self.assertEqual(m.todayLevel, 4)
        self.assertIn("Wind", m.todayDetail)
        self.assertNotIn("Flood", m.todayDetail)


class TestNeedUpdateFingerprint(FrozenTestCase):
    def test_unchanged_data_does_not_flag_update(self):
        entries = make_entry("LU001", "Area", "Yellow Rain Warning issued for Luxembourg - Area",
                              "Moderate rain warning", "Moderate", -1, 3)
        feed = build_feed(entries)
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        self.assertTrue(m.needUpdate, "first call should always flag an update")
        m.processFetchedFeed(feed)
        self.assertFalse(m.needUpdate, "identical second call should not flag an update")

    def test_changed_data_flags_update(self):
        m = make_meteo("LU001")
        feed1 = build_feed(make_entry("LU001", "Area", "Yellow Rain Warning issued for Luxembourg - Area",
                                       "Moderate rain warning", "Moderate", -1, 3))
        m.processFetchedFeed(feed1)
        feed2 = build_feed(make_entry("LU001", "Area", "Red Rain Warning issued for Luxembourg - Area",
                                       "Severe rain warning", "Severe", -1, 3))
        m.processFetchedFeed(feed2)
        self.assertTrue(m.needUpdate)
        self.assertEqual(m.todayLevel, 4)


class TestMultiDaySpan(FrozenTestCase):
    def test_warning_spanning_today_and_tomorrow_appears_in_both(self):
        # onset 1h ago, expires in 30h - spans today AND tomorrow
        entries = make_entry("LU001", "Area", "Orange Rain Warning issued for Luxembourg - Area",
                              "Severe rain warning", "Severe", -1, 30)
        feed = build_feed(entries)
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        self.assertEqual(m.todayLevel, 3)
        self.assertEqual(m.tomorrowLevel, 3)
        self.assertIn("Rain", m.tomorrowDetail)

    def test_warning_ending_today_does_not_appear_tomorrow(self):
        entries = make_entry("LU001", "Area", "Yellow Fog Warning issued for Luxembourg - Area",
                              "Moderate fog warning", "Moderate", -2, 1)
        feed = build_feed(entries)
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        self.assertEqual(m.todayLevel, 2)
        self.assertEqual(m.tomorrowLevel, 1, "should be back to 'no warning' level for tomorrow")


class TestUrgencyTagging(FrozenTestCase):
    def test_future_warning_tagged_upcoming(self):
        entries = make_entry("LU001", "Area", "Yellow Snow Warning issued for Luxembourg - Area",
                              "Moderate snow warning", "Moderate", 20, 30, urgency="Future")
        feed = build_feed(entries)
        m = make_meteo("LU001", detail="detail_dom_lang")
        m.processFetchedFeed(feed)
        self.assertIn("[upcoming]", m.tomorrowDetail)


class TestNoActiveWarnings(FrozenTestCase):
    def test_empty_feed_shows_no_warning_state_not_error(self):
        feed = build_feed("")
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        self.assertFalse(m.hasError)
        self.assertEqual(m.todayLevel, 1)
        # getDayTitle should NOT say ERROR for a legitimately quiet day
        self.assertNotIn("ERROR", m.getTodayTitle())

    def test_no_matching_region_shows_no_warning_state(self):
        entries = make_entry("LU999", "Elsewhere", "Red Wind Warning issued for Luxembourg - Elsewhere",
                              "Severe wind warning", "Severe", -1, 3)
        feed = build_feed(entries)
        m = make_meteo("LU001")  # different code than the one in the feed
        m.processFetchedFeed(feed)
        self.assertFalse(m.hasError)
        self.assertEqual(m.todayLevel, 1)


class TestLanguageMapping(FrozenTestCase):
    def test_swedish_code_is_sv_not_se(self):
        self.assertEqual(meteo.getMeteoLang('sv'), 'Swedish')

    def test_german_lang_index_no_longer_falls_back_to_english(self):
        # regression test for the pre-existing bug: getLangIndex used to
        # check for the native-language words ('deutsch'/'svenska') against
        # the English language names, so this always returned 0
        self.assertEqual(meteo.getLangIndex('German'), 1)
        self.assertEqual(meteo.getLangIndex('Swedish'), 2)

    def test_unmapped_language_falls_back_gracefully(self):
        result = meteo.getMeteoLang('xx')
        self.assertEqual(result, 'English')

    def test_luxembourgish_lang_index(self):
        self.assertEqual(meteo.getLangIndex('Luxembourgish'), 6)

    def test_luxembourgish_translation_used_end_to_end(self):
        entries = make_entry("LU001", "Area", "Red Thunderstorm Warning issued for Luxembourg - Area",
                              "Severe thunderstorm warning", "Severe", -1, 3)
        feed = build_feed(entries)
        m = meteo.Meteo(rssUrl="dummy", rssCode="LU001", domLangSetting="fr",
                         detailSetting="Luxembourgish", iconSetting="icon_no",
                         locationName="Test Location")
        m.processFetchedFeed(feed)
        # "Donnerwieder" is the confirmed Luxembourgish word for thunderstorm
        self.assertIn("Donnerwieder", m.todayDetail)

    def test_luxembourgish_not_auto_detected_from_domoticz_language(self):
        # 'lb' is deliberately not in DOM_LANG_TO_METEO (see comment in
        # meteo.py) - falls back to English rather than erroring
        self.assertEqual(meteo.getMeteoLang('lb'), 'English')


class TestIconKeyLookup(FrozenTestCase):
    def test_icon_key_matches_warning_type_and_level(self):
        entries = make_entry("LU001", "Area", "Red Thunderstorm Warning issued for Luxembourg - Area",
                              "Severe thunderstorm warning", "Severe", -1, 3)
        feed = build_feed(entries)
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        self.assertEqual(m.getDayIconKey(0), "MeteoAlarmEUAtomThunderstormL4")

    def test_no_warning_returns_no_icon(self):
        feed = build_feed("")
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        self.assertIsNone(m.getDayIconKey(0))

    def test_icon_no_setting_is_respected(self):
        # regression test: getDayIconKey() previously ignored self.iconNo
        # entirely, so selecting "NO_ICON" (Mode6) had no effect as long
        # as the icon zip loaded - only the plugin-level iconsLoaded flag
        # gated it, never the user's actual setting.
        entries = make_entry("LU001", "Area", "Red Thunderstorm Warning issued for Luxembourg - Area",
                              "Severe thunderstorm warning", "Severe", -1, 3)
        feed = build_feed(entries)
        m = meteo.Meteo(rssUrl="dummy", rssCode="LU001", domLangSetting="en",
                         detailSetting="detail_dom_lang", iconSetting="icon_no",
                         locationName="Test Location")
        m.processFetchedFeed(feed)
        self.assertEqual(m.todayLevel, 4, "sanity check: the warning itself should still be detected")
        self.assertIsNone(m.getDayIconKey(0), "icon_no should suppress the icon regardless of iconsLoaded")


class TestGeocodeExtraction(FrozenTestCase):
    def test_matches_via_geocode_link(self):
        entries = make_entry("LU001", "Area", "Yellow Wind Warning issued for Luxembourg - Area",
                              "Moderate wind warning", "Moderate", -1, 3)
        feed = build_feed(entries)
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        self.assertEqual(m.todayLevel, 2)

    def test_does_not_false_match_substring(self):
        # LU001 must not match a request for LU00 (substring) - exact match only
        entries = make_entry("LU001", "Area", "Red Wind Warning issued for Luxembourg - Area",
                              "Severe wind warning", "Severe", -1, 3)
        feed = build_feed(entries)
        m = make_meteo("LU00")
        m.processFetchedFeed(feed)
        self.assertEqual(m.todayLevel, 1, "LU00 should not match LU001")


class TestParseRegionCodes(unittest.TestCase):
    def test_splits_on_comma_semicolon_and_whitespace(self):
        self.assertEqual(meteo.parseRegionCodes("LU002, LU001;LU003 LU004"),
                         ['LU002', 'LU001', 'LU003', 'LU004'])

    def test_uppercases_and_deduplicates_keeping_first_position(self):
        self.assertEqual(meteo.parseRegionCodes("lu001, LU002, LU001"), ['LU001', 'LU002'])

    def test_empty_and_none_give_no_codes(self):
        self.assertEqual(meteo.parseRegionCodes(""), [])
        self.assertEqual(meteo.parseRegionCodes(None), [])
        self.assertEqual(meteo.parseRegionCodes(" , ; "), [])


class TestValidateConfig(unittest.TestCase):
    LU_FEED = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-luxembourg"
    IT_FEED = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-italy"

    def test_good_config_has_no_errors_and_no_warnings(self):
        errors, warnings, codes = meteo.validateConfig(self.LU_FEED, "LU002, LU001")
        self.assertEqual((errors, warnings), ([], []))
        self.assertEqual(codes, ['LU002', 'LU001'])

    def test_empty_url_is_an_error(self):
        # the exact misconfiguration seen in the 2026-09-11 log
        errors, _, _ = meteo.validateConfig("", "IT001")
        self.assertEqual(len(errors), 1)
        self.assertIn("RSSFeed", errors[0])

    def test_non_http_url_is_an_error(self):
        errors, _, _ = meteo.validateConfig("ftp://example.org/feed", "LU001")
        self.assertEqual(len(errors), 1)

    def test_empty_codes_is_an_error(self):
        errors, _, _ = meteo.validateConfig(self.LU_FEED, " , ")
        self.assertEqual(len(errors), 1)
        self.assertIn("RSSCode", errors[0])

    def test_both_problems_are_reported_together(self):
        errors, _, _ = meteo.validateConfig("", "")
        self.assertEqual(len(errors), 2)

    def test_old_numeric_rss_code_only_warns(self):
        errors, warnings, codes = meteo.validateConfig(self.LU_FEED, "202")
        self.assertEqual(errors, [], "a suspicious code must never block start-up")
        self.assertEqual(codes, ['202'])
        self.assertEqual(len(warnings), 1)
        self.assertIn("202", warnings[0])

    def test_code_from_another_country_warns(self):
        errors, warnings, _ = meteo.validateConfig(self.IT_FEED, "LU001")
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("IT", warnings[0])

    def test_unknown_country_slug_skips_the_prefix_check(self):
        url = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-atlantis"
        self.assertEqual(meteo.validateConfig(url, "XX001")[1], [])

    def test_foreign_host_and_non_atom_url_only_warn(self):
        errors, warnings, _ = meteo.validateConfig("https://example.org/feed.xml", "LU001")
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        errors, warnings, _ = meteo.validateConfig("https://feeds.meteoalarm.org/feeds/rss-luxembourg", "LU001")
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)


class TestPublishedStamp(FrozenTestCase):
    """since 1.7.2 the publish time lives at the end of the device text"""

    def test_published_today_shows_hh_mm(self):
        feed = build_feed(make_entry("LU001", "Area", "Red Wind Warning issued for Luxembourg - Area",
                                      "Severe wind warning", "Severe", -1, 3))
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        self.assertTrue(m.todayDetail.endswith(" [12:00]"), m.todayDetail)

    def test_compact_mode_gets_the_stamp_too(self):
        feed = build_feed(make_entry("LU001", "Area", "Red Wind Warning issued for Luxembourg - Area",
                                      "Severe wind warning", "Severe", -1, 3))
        m = make_meteo("LU001", detail="no_detail")
        m.processFetchedFeed(feed)
        self.assertEqual(m.todayDetail, "Wind (4) [12:00]")

    def test_published_another_day_shows_the_date(self):
        feed = build_feed(make_entry("LU001", "Area", "Red Wind Warning issued for Luxembourg - Area",
                                      "Severe wind warning", "Severe", -1, 3, published_offset_hours=-24))
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        expected = "{:%d.%m. 12:00}".format(clock_now() - timedelta(days=1))
        self.assertTrue(m.todayDetail.endswith(" [{}]".format(expected)), m.todayDetail)

    def test_newest_message_of_the_day_wins(self):
        entries = (
            make_entry("LU001", "Area", "Yellow Rain Warning issued for Luxembourg - Area",
                       "Moderate rain warning", "Moderate", -3, 3, published_offset_hours=-3) +
            make_entry("LU001", "Area", "Red Wind Warning issued for Luxembourg - Area",
                       "Severe wind warning", "Severe", -1, 3, published_offset_hours=-1))
        m = make_meteo("LU001")
        m.processFetchedFeed(build_feed(entries))
        self.assertTrue(m.todayDetail.endswith(" [11:00]"), m.todayDetail)

    def test_no_warning_day_has_no_stamp(self):
        m = make_meteo("LU001")
        m.processFetchedFeed(build_feed(""))
        self.assertNotIn("[", m.todayDetail)

    def test_fingerprint_changes_when_a_message_is_republished(self):
        m = make_meteo("LU001")
        m.processFetchedFeed(build_feed(make_entry(
            "LU001", "Area", "Red Wind Warning issued for Luxembourg - Area",
            "Severe wind warning", "Severe", -1, 3, published_offset_hours=-2)))
        m.processFetchedFeed(build_feed(make_entry(
            "LU001", "Area", "Red Wind Warning issued for Luxembourg - Area",
            "Severe wind warning", "Severe", -1, 3, published_offset_hours=-1)))
        self.assertTrue(m.needUpdate)

    def test_time_is_local_not_utc(self):
        # regression: feedparser's *_parsed values are UTC and time.mktime()
        # reads them as local time, which showed the UTC clock time. Run in
        # a zone that is not UTC+0/+1 so the difference is visible anywhere.
        previous = os.environ.get('TZ')

        def restoreZone():
            if previous is None:
                os.environ.pop('TZ', None)
            else:
                os.environ['TZ'] = previous
            time.tzset()
        self.addCleanup(restoreZone)
        os.environ['TZ'] = 'IST-5:30'
        time.tzset()
        self.addCleanup(freeze(noon_today()))

        feed = build_feed(make_entry("LU001", "Area", "Red Wind Warning issued for Luxembourg - Area",
                                      "Severe wind warning", "Severe", -1, 3))
        m = make_meteo("LU001")
        m.processFetchedFeed(feed)
        self.assertTrue(m.todayDetail.endswith(" [12:00]"), m.todayDetail)
        self.assertIn("(12:00)", m.getTodayTitle())


class _FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self._status = status

    def getcode(self):
        return self._status

    def read(self):
        return self._body


class TestFetchFeedGuard(unittest.TestCase):
    """feedparser never raises on bad input - fetchFeed must not read a
    non-feed 200 response as 'no warnings'"""

    def _fetch(self, body):
        from unittest import mock
        with mock.patch.object(meteo.urllib.request, 'urlopen', return_value=_FakeResponse(body)):
            return meteo.fetchFeed("https://feeds.meteoalarm.org/x", 5)

    def test_html_page_with_status_200_is_rejected(self):
        with self.assertRaises(Exception) as ctx:
            self._fetch(b"<html><body>Please log in to the guest wifi</body></html>")
        self.assertIn("not a valid Atom feed", str(ctx.exception))

    def test_empty_body_is_rejected(self):
        with self.assertRaises(Exception):
            self._fetch(b"")

    def test_a_feed_in_an_unrecognised_dialect_is_still_accepted_if_it_has_feed_elements(self):
        # fail-safe: the guard must never refuse a real feed. It needs BOTH
        # "no recognised format" and "no title/id/updated" to reject.
        body = (b'<?xml version="1.0"?><feed xmlns="http://example.org/odd">'
                b'<title>Luxembourg</title></feed>')
        feed, _ = self._fetch(body)
        self.assertEqual(len(feed['entries']), 0)

    def test_valid_feed_without_warnings_is_accepted(self):
        body = (b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<feed xmlns="http://www.w3.org/2005/Atom"><id>x</id><title>Luxembourg</title>'
                b'<updated>2026-11-02T10:00:00Z</updated></feed>')
        feed, raw = self._fetch(body)
        self.assertEqual(len(feed['entries']), 0)
        self.assertEqual(raw, body)


if __name__ == '__main__':
    unittest.main(verbosity=2)

