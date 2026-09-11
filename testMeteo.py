"""
testMeteo.py - test entry point for meteo.py, runnable outside Domoticz
via fakeDomoticz.py (per the pattern from ffes/domoticz-buienradar
referenced in the README).

Run with:
    python3 testMeteo.py

These tests build synthetic CAP-Atom feed XML with dates relative to the
actual time the test runs (never hardcoded past dates), so they stay
valid indefinitely rather than silently testing against stale/expired
sample data.
"""
import unittest
import tempfile
import os
from datetime import datetime, timedelta

import feedparser
import meteo


def iso(dt):
    s = dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    return s[:-2] + ':' + s[-2:]


def build_feed(entries_xml):
    now = datetime.now().astimezone()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
  <id>tag:meteoalarm.org,test:LU</id><title>Test feed</title>
  <updated>{updated}</updated>
  {entries}
</feed>""".format(updated=now.strftime('%Y-%m-%dT%H:%M:%SZ'), entries=entries_xml)
    fd, path = tempfile.mkstemp(suffix='.xml')
    with os.fdopen(fd, 'w') as f:
        f.write(xml)
    try:
        return feedparser.parse(path)
    finally:
        os.remove(path)


def make_entry(code, area, title, event, severity, onset_offset_hours,
                expires_offset_hours, urgency="Immediate", status="Actual",
                certainty="Likely"):
    now = datetime.now().astimezone()
    onset = now + timedelta(hours=onset_offset_hours)
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
                      pub=now.strftime('%Y-%m-%dT%H:%M:%SZ'), event_id=abs(hash(title)) % 10000)


def make_meteo(code, lang="en", detail="detail_dom_lang", location="Test Location"):
    return meteo.Meteo(rssUrl="dummy", rssCode=code, domLangSetting=lang,
                        detailSetting=detail, iconSetting="icon_inline_detail",
                        locationName=location)


class TestCapStatusFiltering(unittest.TestCase):
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


class TestNeedUpdateFingerprint(unittest.TestCase):
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


class TestMultiDaySpan(unittest.TestCase):
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


class TestUrgencyTagging(unittest.TestCase):
    def test_future_warning_tagged_upcoming(self):
        entries = make_entry("LU001", "Area", "Yellow Snow Warning issued for Luxembourg - Area",
                              "Moderate snow warning", "Moderate", 20, 30, urgency="Future")
        feed = build_feed(entries)
        m = make_meteo("LU001", detail="detail_dom_lang")
        m.processFetchedFeed(feed)
        self.assertIn("[upcoming]", m.tomorrowDetail)


class TestNoActiveWarnings(unittest.TestCase):
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


class TestLanguageMapping(unittest.TestCase):
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


class TestIconKeyLookup(unittest.TestCase):
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


class TestGeocodeExtraction(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main(verbosity=2)

