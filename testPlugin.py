"""
testPlugin.py - end-to-end tests: drive plugin.py's onStart()/onHeartbeat()
against fakeDomoticz.py with a controllable clock and a scripted feed, and
assert on the Domoticz devices and log lines that come out.

Run with:
    python3 -m unittest testPlugin

Nothing here touches the network: meteo.fetchFeed is replaced by a script
(a feed, or an exception, per call) and the clock is frozen and advanced by
hand, so a "3 hour outage" runs in milliseconds and the tests give the same
result at any time of day.
"""
import os
import shutil
import tempfile
import unittest
import zipfile
from datetime import timedelta
from unittest import mock

import fakeDomoticz
import meteo
import plugin
import testMeteo as tm

HERE = os.path.dirname(os.path.abspath(__file__))
LU_FEED = "https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-luxembourg"


def red_wind(code="LU002", onset=-1, expires=30):
    """a red wind warning from 11:00 today to 18:00 tomorrow (the clock is
    frozen at 12:00), so it is on both the Today and the Tomorrow device"""
    return tm.make_entry(code, "Area", "Red Wind Warning issued for Luxembourg - Area",
                         "Severe wind warning", "Severe", onset, expires)


class PluginTestCase(unittest.TestCase):
    """a plugin instance wired to the fake Domoticz, a frozen clock and a
    scripted feed. Defaults to the manifest defaults except Mode5/Mode6."""

    def setUp(self):
        fakeDomoticz.reset()
        previousDir = os.getcwd()
        self.addCleanup(os.chdir, previousDir)
        os.chdir(HERE)  # fakeDomoticz opens the icon zip relative to the cwd

        self.params = {
            "Mode1": LU_FEED, "Mode2": "LU002, LU001", "Mode3": "30", "Mode4": "Normal",
            "Mode5": "English", "Mode6": "icon_no", "Name": "Meteo Alarm", "HomeFolder": HERE + os.sep,
        }
        plugin.Parameters = self.params
        plugin.Settings = {"Language": "en"}
        plugin.Devices = fakeDomoticz.Devices
        plugin.Images = fakeDomoticz.Images

        self.addCleanup(tm.freeze(tm.noon_today(), plugin))

        # scripted feed: set self.feed to a feedparser result, or to an
        # Exception instance to make the fetch fail
        self.feed = tm.build_feed("")
        self.fetchTimes = []
        patcher = mock.patch.object(meteo, "fetchFeed", side_effect=self._fetch)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.p = None

    # -- scripting helpers ------------------------------------------------

    def _fetch(self, url, timeout):
        self.fetchTimes.append(tm.FrozenDatetime._now)
        if isinstance(self.feed, Exception):
            raise self.feed
        return self.feed, b""

    def start(self):
        self.p = plugin.BasePlugin()
        plugin._plugin = self.p
        self.p.onStart()
        return self.p

    def advance(self, **delta):
        tm.FrozenDatetime._now = tm.FrozenDatetime._now + timedelta(**delta)

    def beat(self, **delta):
        if delta:
            self.advance(**delta)
        self.p.onHeartbeat()

    def beats(self, total_seconds, step_seconds=10):
        """heartbeats every `step_seconds` for `total_seconds` of simulated time"""
        for _ in range(total_seconds // step_seconds):
            self.beat(seconds=step_seconds)

    def setClock(self, hour, minute=0):
        tm.FrozenDatetime._now = tm.FrozenDatetime._now.replace(hour=hour, minute=minute, second=0)

    @staticmethod
    def dev(unit):
        return fakeDomoticz.Devices[unit]

    def seedDevice(self, unit, name, nValue=0, sValue="", typeName="Alert"):
        d = fakeDomoticz.Device(Name=name, Unit=unit, TypeName=typeName, Used=1).Create()
        d.nValue, d.sValue = nValue, sValue
        return d

    def levels(self, *units):
        return [self.dev(u).nValue for u in units]

    def pluginErrors(self):
        return fakeDomoticz.errors()


class TestFirstStart(PluginTestCase):
    def test_fresh_install_creates_region_named_devices_in_a_grey_starting_state(self):
        self.start()
        self.assertEqual(sorted(fakeDomoticz.Devices), [1, 2, 3, 4, 5, 6])
        self.assertEqual(self.dev(1).Name, "Today (LU002)")
        self.assertEqual(self.dev(2).Name, "Tomorrow (LU002)")
        self.assertEqual(self.dev(5).Name, "Today (LU001)")
        self.assertEqual(self.dev(6).Name, "Tomorrow (LU001)")
        self.assertEqual(self.dev(3).Name, "Plugin Status")
        self.assertEqual((self.dev(3).nValue, self.dev(3).sValue), (plugin.LEVEL_GREY, "Starting"))
        self.assertEqual(self.dev(1).sValue, "No Data")
        self.assertEqual(self.dev(4).sValue, "never")

    def test_status_is_not_ok_before_the_first_successful_fetch(self):
        self.start()
        self.assertNotEqual(self.dev(3).sValue, "OK")
        self.assertEqual(self.fetchTimes, [], "onStart itself must not fetch")

    def test_first_heartbeat_fetches_and_turns_status_green(self):
        self.feed = tm.build_feed(red_wind("LU002"))
        self.start()
        self.beat()
        self.assertEqual(len(self.fetchTimes), 1)
        self.assertEqual((self.dev(3).nValue, self.dev(3).sValue), (plugin.LEVEL_GREEN, "OK"))
        self.assertEqual(self.levels(1, 2, 5, 6), [4, 4, 1, 1])
        self.assertEqual(self.dev(4).sValue, "{:%Y-%m-%d %H:%M:%S}".format(plugin.datetime.now()))

    def test_publish_time_is_part_of_the_device_text_not_the_name(self):
        self.feed = tm.build_feed(red_wind("LU002"))
        self.start()
        self.beat()
        self.assertTrue(self.dev(1).sValue.endswith(" [12:00]"), self.dev(1).sValue)
        self.assertEqual(self.dev(1).Name, "Today (LU002)")


class TestFeedProblems(PluginTestCase):
    def setUp(self):
        super().setUp()
        self.goodFeed = tm.build_feed(red_wind("LU002"))
        self.feed = self.goodFeed
        self.start()
        self.beat()  # a good fetch at 12:00 -> Today(LU002) is red (level 4)
        self.assertEqual(self.levels(1, 2), [4, 4])

    def test_a_failed_fetch_never_paints_today_or_tomorrow_red(self):
        self.feed = tm.build_feed("")      # next good data says: all clear
        self.beat(minutes=30)              # ... fetched at 12:30 -> level 1
        self.assertEqual(self.levels(1, 2, 5, 6), [1, 1, 1, 1])
        before = {u: len(self.dev(u).history) for u in (1, 2, 5, 6)}
        self.feed = Exception("could not reach feed: timed out")
        fetchesBefore = len(self.fetchTimes)
        self.beats(40 * 60)                # 12:30 -> 13:10: the next poll (13:00) fails, then retries
        self.assertGreaterEqual(len(self.fetchTimes) - fetchesBefore, 3,
                                "the test must really exercise failing fetches")
        for unit in (1, 2, 5, 6):
            self.assertEqual(len(self.dev(unit).history), before[unit], "unit {} was written".format(unit))
            self.assertNotEqual(self.dev(unit).nValue, 4)

    def test_failing_fetch_keeps_last_values_and_shows_orange_retrying(self):
        self.feed = Exception("HTTP error 503 fetching feed")
        self.beat(minutes=30)
        self.assertEqual(self.levels(1, 2), [4, 4], "the last real data stays visible")
        self.assertEqual(self.dev(3).nValue, plugin.LEVEL_ORANGE)
        self.assertTrue(self.dev(3).sValue.startswith("Retrying (attempt 1)"), self.dev(3).sValue)
        self.assertIn("503", self.dev(3).sValue)

    def test_today_and_tomorrow_turn_grey_after_three_poll_intervals(self):
        self.feed = Exception("could not reach feed")
        self.beats(89 * 60, 60)            # 12:00 + 89 min
        self.assertEqual(self.levels(1, 2), [4, 4], "89 min < 3 x 30 min: still fresh")
        self.assertEqual(self.dev(3).nValue, plugin.LEVEL_ORANGE)
        self.beats(60, 60)                 # 90 min since the last good fetch
        self.assertEqual(self.levels(1, 2, 5, 6), [0, 0, 0, 0])
        self.assertIn("since 12:00", self.dev(1).sValue)
        self.assertEqual(self.dev(3).nValue, plugin.LEVEL_RED)
        self.assertTrue(self.dev(3).sValue.startswith("FAILING since 12:00"), self.dev(3).sValue)

    def test_recovery_restores_values_and_status_even_if_the_data_is_unchanged(self):
        self.feed = Exception("could not reach feed")
        self.beats(100 * 60, 60)
        self.assertEqual(self.levels(1, 2), [0, 0])
        self.feed = self.goodFeed          # the very same feed as before the outage: nothing changed
        self.beats(60 * 60, 60)
        self.assertEqual(self.levels(1, 2), [4, 4], "grey must not stick when the data did not change")
        self.assertEqual((self.dev(3).nValue, self.dev(3).sValue), (plugin.LEVEL_GREEN, "OK"))
        self.assertTrue(any("recovered" in t for lvl, t in fakeDomoticz.messages if lvl == "LOG"))

    def test_processing_failure_in_one_region_does_not_turn_anything_red(self):
        real = meteo.Meteo.processFetchedFeed

        def flaky(meteoSelf, feed):
            if meteoSelf.rssCode == "LU001":
                meteoSelf.setError("boom")
                return
            return real(meteoSelf, feed)
        with mock.patch.object(meteo.Meteo, "processFetchedFeed", flaky):
            self.beat(minutes=30)
        self.assertEqual(self.levels(5, 6), [1, 1], "LU001 keeps what it showed after the good fetch in setUp")
        self.assertEqual(self.dev(3).nValue, plugin.LEVEL_ORANGE)
        self.assertIn("LU001", self.dev(3).sValue)
        self.assertEqual(self.levels(1, 2), [4, 4])


class TestRetryBackoff(PluginTestCase):
    def test_retries_follow_the_step_table_not_every_heartbeat(self):
        self.feed = Exception("could not reach feed")
        self.start()
        self.beats(30 * 60 - 10, 10)       # 30 minutes of 10-second heartbeats
        start = self.fetchTimes[0]
        offsets = [int((t - start).total_seconds()) for t in self.fetchTimes]
        # attempt 1 at once, then waits of 60, 120, 300 and 600 seconds
        self.assertEqual(offsets, [0, 60, 180, 480, 1080])

    def test_wait_never_exceeds_the_poll_interval(self):
        self.feed = Exception("could not reach feed")
        self.start()
        self.beats(6 * 3600, 60)
        gaps = [int((b - a).total_seconds()) for a, b in zip(self.fetchTimes, self.fetchTimes[1:])]
        self.assertLessEqual(max(gaps), 30 * 60)
        self.assertEqual(gaps[-1], 30 * 60)

    def test_repeating_failures_do_not_flood_the_log(self):
        self.feed = Exception("could not reach feed")
        self.start()
        self.beats(24 * 3600, 60)
        attempts = len(self.fetchTimes)
        failureLines = [e for e in self.pluginErrors() if e.startswith("Feed fetch failed")]
        self.assertGreater(attempts, 40)
        self.assertLessEqual(len(failureLines), len(plugin.RETRY_STEPS_SECONDS),
                             "{} failure lines for {} attempts".format(len(failureLines), attempts))

    def test_a_changed_error_message_is_logged_again(self):
        self.feed = Exception("could not reach feed")
        self.start()
        self.beats(24 * 3600, 60)
        before = len([e for e in self.pluginErrors() if e.startswith("Feed fetch failed")])
        self.feed = Exception("HTTP error 503 fetching feed")
        self.beats(3600, 60)
        after = len([e for e in self.pluginErrors() if e.startswith("Feed fetch failed")])
        self.assertGreater(after, before)


class TestConfigurationErrors(PluginTestCase):
    def test_empty_url_is_reported_once_and_never_polled(self):
        # the exact misconfiguration of the 2026-09-11 log: Error #0..#19 every 10 s
        self.params["Mode1"] = ""
        self.start()
        errorsAfterStart = list(self.pluginErrors())
        self.beats(3600, 10)
        self.assertEqual(self.fetchTimes, [], "must not try to fetch an empty URL")
        self.assertEqual(self.pluginErrors(), errorsAfterStart, "no further log lines after start-up")
        self.assertEqual(len([e for e in errorsAfterStart if e.startswith("Configuration error")]), 1)
        self.assertEqual(self.dev(3).nValue, plugin.LEVEL_RED)
        self.assertTrue(self.dev(3).sValue.startswith("CONFIG ERROR"), self.dev(3).sValue)

    def test_empty_region_codes_is_a_configuration_error(self):
        self.params["Mode2"] = " , "
        self.start()
        self.beats(600, 10)
        self.assertEqual(self.fetchTimes, [])
        self.assertIn("RSSCode", self.dev(3).sValue)

    def test_config_error_creates_only_the_status_devices(self):
        self.params["Mode1"] = ""
        self.start()
        self.assertEqual(sorted(fakeDomoticz.Devices), [3, 4])

    def test_suspicious_region_code_only_warns_and_still_polls(self):
        self.params["Mode2"] = "202"
        self.start()
        self.beat()
        self.assertEqual(len(self.fetchTimes), 1)
        self.assertTrue(any("202" in e for e in self.pluginErrors()))
        self.assertEqual(self.dev(3).sValue, "OK")

    def test_region_list_is_cleaned_up_before_use(self):
        self.params["Mode2"] = "lu002;LU001 , lu002"
        self.start()
        self.assertEqual(sorted(fakeDomoticz.Devices), [1, 2, 3, 4, 5, 6])
        self.assertEqual(self.dev(5).Name, "Today (LU001)")

    def test_poll_interval_is_validated_and_clamped(self):
        self.assertEqual(plugin.parsePollMinutes("45"), (45, []))
        self.assertEqual(plugin.parsePollMinutes("2")[0], plugin.MIN_POLL_MINUTES)
        self.assertEqual(plugin.parsePollMinutes("99999")[0], plugin.MAX_POLL_MINUTES)
        minutes, problems = plugin.parsePollMinutes("")
        self.assertEqual(minutes, plugin.DEFAULT_POLL_MINUTES)
        self.assertEqual(len(problems), 1)
        self.assertEqual(plugin.parsePollMinutes(None)[0], plugin.DEFAULT_POLL_MINUTES)

    def test_invalid_poll_interval_falls_back_to_30_minutes_and_still_starts(self):
        self.params["Mode3"] = "abc"
        self.start()
        self.assertEqual(self.p.pollinterval, 30 * 60)
        self.assertEqual(sorted(fakeDomoticz.Devices), [1, 2, 3, 4, 5, 6])


class TestRestartAndNaming(PluginTestCase):
    def test_restart_keeps_existing_values_and_last_update(self):
        self.seedDevice(1, "Meteo Alarm - Today (LU002)", 4, "Wind (4) [11:00]")
        self.seedDevice(2, "Meteo Alarm - Tomorrow (LU002)", 1, "No special awareness required")
        self.seedDevice(3, "Meteo Alarm - Plugin Status", 1, "OK")
        self.seedDevice(4, "Meteo Alarm - Last Successful Update", 0, "2026-11-02 11:00:00", "Text")
        self.start()
        self.assertEqual((self.dev(1).nValue, self.dev(1).sValue), (4, "Wind (4) [11:00]"))
        self.assertEqual((self.dev(2).nValue, self.dev(2).sValue), (1, "No special awareness required"))
        self.assertEqual(self.dev(4).sValue, "2026-11-02 11:00:00")
        self.assertEqual((self.dev(3).nValue, self.dev(3).sValue), (plugin.LEVEL_GREY, "Starting"))

    def test_only_brand_new_devices_get_a_placeholder(self):
        self.seedDevice(1, "Meteo Alarm - Today (LU002)", 3, "kept")
        self.start()
        self.assertEqual(self.dev(1).sValue, "kept")
        self.assertEqual(self.dev(2).sValue, "No Data")

    def test_legacy_names_are_migrated_and_custom_names_are_kept(self):
        self.seedDevice(1, "Meteo Alarm - Today", 4, "Wind (4)")                         # 1.7.0 name
        self.seedDevice(2, "Meteo Alarm - Wetter morgen", 2, "Rain (2)")                  # chosen by the user
        self.seedDevice(5, "Meteo Alarm - Today: Luxembourg (14:05)", 3, "Fog (3)")        # 1.7.0 feed-title name
        self.seedDevice(6, "Meteo Alarm - Tomorrow (LU002)", 1, "ok")                     # region order changed
        self.start()
        self.assertEqual(self.dev(1).Name, "Today (LU002)")
        self.assertEqual(self.dev(2).Name, "Meteo Alarm - Wetter morgen")
        self.assertEqual(self.dev(5).Name, "Today (LU001)")
        self.assertEqual(self.dev(6).Name, "Tomorrow (LU001)")
        # the one-time rename must not touch the values
        self.assertEqual((self.dev(1).nValue, self.dev(1).sValue), (4, "Wind (4)"))
        self.assertEqual((self.dev(5).nValue, self.dev(5).sValue), (3, "Fog (3)"))

    def test_localised_legacy_names_are_recognised(self):
        self.seedDevice(1, "Meteo Alarm - Heute: Luxemburg (14:05)", 1, "x")
        self.seedDevice(2, "Meteo Alarm - Demain: ERROR!!!", 1, "x")
        self.start()
        self.assertEqual(self.dev(1).Name, "Today (LU002)")
        self.assertEqual(self.dev(2).Name, "Tomorrow (LU002)")

    def test_isPluginGeneratedName(self):
        for name in ("Today", "Today (LU002)", "Tomorrow", "Tomorrow (LU001)", "Today: Luxembourg (14:05)",
                     "Heute: ERROR!!!", "Idag", "Aujourd'hui: Luxembourg"):
            self.assertTrue(plugin.isPluginGeneratedName(name), name)
        for name in ("Wetter heute", "Garden", "Today - Garden", "Plugin Status", ""):
            self.assertFalse(plugin.isPluginGeneratedName(name), name)

    def test_updates_never_rename_a_device(self):
        self.feed = tm.build_feed(red_wind("LU002"))
        self.start()
        self.dev(1).Name = "Meteo Alarm - My Wind Alarm"      # the user renames it in the GUI
        self.beat()
        self.beat(minutes=30)
        self.assertEqual(self.dev(1).Name, "Meteo Alarm - My Wind Alarm")
        for unit, device in fakeDomoticz.Devices.items():
            self.assertTrue(all(name is None for _, _, name in device.history),
                            "unit {} was updated with a Name".format(unit))


class TestMidnight(PluginTestCase):
    def test_rolls_over_to_the_new_day_without_a_new_request(self):
        self.params["Mode3"] = "300"       # a long interval: the next poll is 5 hours away
        self.setClock(23, 30)
        # a warning for tomorrow only: 08:00 - 20:00
        self.feed = tm.build_feed(red_wind("LU002", onset=8.5, expires=20.5))
        self.start()
        self.beat()
        self.assertEqual(len(self.fetchTimes), 1)
        self.assertEqual(self.levels(1, 2), [1, 4], "tomorrow is red, today is quiet")
        self.beat(minutes=40)              # 00:10 next day
        self.assertEqual(len(self.fetchTimes), 1, "the rollover must not trigger a request")
        self.assertEqual(self.levels(1, 2), [4, 1], "yesterday's Tomorrow is today's Today")

    def test_nothing_happens_within_the_same_day(self):
        self.params["Mode3"] = "300"
        self.feed = tm.build_feed(red_wind("LU002"))
        self.start()
        self.beat()
        history = len(self.dev(1).history)
        self.beat(minutes=60)
        self.assertEqual(len(self.dev(1).history), history)

    def test_stale_data_is_not_revived_by_the_rollover(self):
        self.setClock(23, 0)
        self.feed = tm.build_feed(red_wind("LU002", onset=-1, expires=30))
        self.start()
        self.beat()
        self.assertEqual(self.levels(1, 2), [4, 4])
        self.feed = Exception("could not reach feed")
        self.beats(150 * 60, 60)           # 01:30 next day: well past 3 x 30 min
        self.assertEqual(self.levels(1, 2), [0, 0])
        self.beats(30 * 60, 60)
        self.assertEqual(self.levels(1, 2), [0, 0], "cached feed must not overwrite the grey 'no data' state")


class TestIcons(PluginTestCase):
    def test_shipped_zip_loads_and_icons_are_applied(self):
        self.params["Mode6"] = "icon_inline"
        self.feed = tm.build_feed(tm.make_entry(
            "LU002", "Area", "Red Thunderstorm Warning issued for Luxembourg - Area",
            "Severe thunderstorm warning", "Severe", -1, 3))
        self.start()
        self.assertTrue(self.p.iconsLoaded)
        self.assertIn(plugin.ICON_PROBE_NAME, fakeDomoticz.Images)
        self.beat()
        self.assertEqual(self.dev(1).LastImage, fakeDomoticz.Images["MeteoAlarmEUAtomThunderstormL4"].ID)

    def test_zip_packed_with_a_subfolder_fails_visibly_and_the_plugin_still_works(self):
        # what a zip made on macOS looks like: everything inside a folder
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        with zipfile.ZipFile(os.path.join(HERE, plugin.ICON_ZIP_FILENAME)) as good, \
                zipfile.ZipFile(os.path.join(tmp, plugin.ICON_ZIP_FILENAME), "w") as bad:
            for name in good.namelist():
                bad.writestr("meteoalarm_icons/" + name, good.read(name))
        os.chdir(tmp)
        self.params["HomeFolder"] = tmp + os.sep
        self.params["Mode6"] = "icon_inline"
        self.feed = tm.build_feed(red_wind("LU002"))
        self.start()
        self.assertFalse(self.p.iconsLoaded)
        self.assertTrue(any("Could not load custom icons" in e for e in self.pluginErrors()))
        self.beat()
        self.assertEqual(self.levels(1, 2), [4, 4], "warnings still work without icons")


if __name__ == "__main__":
    unittest.main(verbosity=2)
