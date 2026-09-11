# MeteoAlarmEU-Atom

[![Plugin version](https://img.shields.io/badge/version-1.7.1-red.svg)]()
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

Show official weather warnings from [meteoalarm.org](http://www.meteoalarm.org/)
as devices in your [Domoticz](https://www.domoticz.com/) home automation
install.

![settings](https://github.com/belzetrigger/domoticz-MeteoAlarmEU/raw/master/resources/unit_en_ml_warnings.PNG)

> **New here?** For installation steps, see [`DEPLOY.md`](DEPLOY.md).
> For the version history, see [`CHANGELOG.md`](CHANGELOG.md).
> For security/reporting info, see [`SECURITY.md`](SECURITY.md).
> This file covers what the plugin does, its settings, and how it works.

---

## What this is

A Domoticz virtual hardware plugin that turns
[meteoalarm.org](http://www.meteoalarm.org/)'s official European weather
warnings into Domoticz devices you can dashboard, automate on, or get
notified from — no manual checking of a weather site required.

Since this is a European meteorological alerting network, it only
covers Europe — check [meteoalarm.org](https://meteoalarm.org) to
confirm your country participates.

> **Note on naming:** meteoalarm.org sunset its legacy RSS feeds in
> favour of an Atom-based CAP feed (see `CHANGELOG.md` 1.6.0/1.6.3).
> This fork tracks that change and is maintained separately from the
> original [belzetrigger/domoticz-MeteoAlarmEU](https://github.com/belzetrigger/domoticz-MeteoAlarmEU),
> which itself is a fork of [ycahome/MeteoAlarmEU](https://github.com/ycahome/MeteoAlarmEU).
> Licensed GPL-3.0, same as upstream — see [`LICENSE`](LICENSE).

## Devices it creates

| Device | Purpose |
| --- | --- |
| **Today** / **Tomorrow** | Alert-level devices for your primary configured region |
| **Plugin Status** | Reflects whether the last feed fetch succeeded — wire a Domoticz notification off this without parsing alert text |
| **Last Successful Update** | Timestamp of the last clean fetch, so a silently stuck feed is visible in the UI, not just in logs |
| **Today (\<code\>)** / **Tomorrow (\<code\>)** | One extra pair per additional region configured (1.7.0+) |

## Settings

| Field | What it does |
| --- | --- |
| **RSSFeed** | Your country's Atom feed URL from [feeds.meteoalarm.org](https://feeds.meteoalarm.org/) — must be a `...legacy-atom-<country>` URL. Legacy RSS URLs are sunset and no longer work. |
| **RSSCode (primary region)** | Your region's `EMMA_ID` code (e.g. `LU001`). Get it from meteoalarm.org's "geocodes json" download, or from an old-style RSS filename like `FI001.rss` → `FI001`. |
| **Additional Region Codes** *(1.7.0+)* | Optional, comma-separated (e.g. `LU002,LU003`). Must be regions within the **same** country/feed as RSSFeed — one fetch per heartbeat is shared across all of them. For a different country, add the hardware a second time instead. |
| **Update** | Minutes between polls. Falls back to 300 if missing/invalid rather than failing to start. |
| **Debug** | Verbose logging — includes a raw-feed preview on fetch/parse failure and feedparser's own malformed-feed warnings. |
| **Details and Language** | `NO_DETAIL` (compact), `Details using domoticz lang` (auto-detects from Domoticz's own language setting), or an explicit language: English, German, Swedish, French, Spanish, Finnish, or **Luxembourgish** *(1.7.1+)*. |
| **Show Alarm Icons** | *(1.7.0+)* Controls the plugin's own bundled severity+type icon set, since the feed itself no longer provides icons. `NO_ICON` uses Domoticz's default Alert icon. |

## How it works

The feed is parsed directly from its structured CAP fields (verified by
fetching the live feed and inspecting it — the previous HTML-table-based
format the feed used to serve is gone). For each configured region:

- **Matching** — the region code is matched exactly against the entry's
  `geocode=EMMA_ID:...` link (not by substring), so e.g. `LU00` won't
  falsely match `LU001`.
- **Filtering** — only `cap:status: Actual` entries count; `Test`,
  `Exercise`, `Draft`, and `System` CAP messages are excluded.
- **Classification** — warning type (thunderstorm/rain/wind/etc.) and
  colour level (green/yellow/orange/red) come from the entry title and
  `cap:severity`, translated via the plugin's own built-in language
  table — independent of what language the feed itself publishes in
  (currently English only).
- **Day-splitting** — `cap:onset`/`cap:expires` (real timestamps) decide
  whether a warning belongs to Today, Tomorrow, or both. A warning
  spanning multiple days appears in both, with the non-today end shown
  as a date + day-offset (e.g. `+1d`).
- **Urgency** — `cap:urgency` of `Future`/`Past` shows as
  `[upcoming]`/`[ending]` in verbose mode.
- **Change detection** — devices only update when the rendered
  today/tomorrow text or level actually changed, not on every poll.

The feed fetch has a 15-second timeout so a hung connection can't block
Domoticz's whole heartbeat cycle, and multiple regions share a single
fetch per heartbeat rather than each fetching independently.

## Bugs and ToDos

1. **Icon zip is unverified against a live Domoticz instance.**
   `meteoalarm_icons.zip` was built against Domoticz's documented
   custom-icon conventions and a simulated test harness, but real-world
   behavior for plugin-bundled icons on Alert-type devices specifically
   has conflicting documentation even within the Domoticz community. If
   icons don't appear, the plugin still works normally (default Alert
   icon) — see `DEPLOY.md` → *Verifying It's Running Correctly*.
2. Event-type detection is keyword-matching against the entry title and
   `cap:event`. Only Thunderstorm, Rain, Coastal Event, and Forest-fire
   are confirmed against real feed data; Wind, Snow/Ice, Fog, High/Low
   Temp, Avalanches, and Flood follow MeteoAlarm's documented category
   list but aren't yet confirmed against a live warning.
3. Two Luxembourgish translations (**Coastal Event**, **Avalanches**)
   are constructed rather than attested, since neither is a real
   Luxembourg weather phenomenon with existing native vocabulary — a
   native-speaker check would help.
4. Multi-region support only covers regions within the same
   country/feed. Different countries still need a separate hardware
   instance.
5. `cap:certainty` and `cap:message_type` (Alert vs Update) are fetched
   but not yet surfaced anywhere — only `cap:urgency` made it into the
   display.
6. Idea, not yet built: trigger Domoticz automations directly off
   warnings (e.g. close blinds on a wind warning, delay garden
   watering on a rain warning) — currently you'd build that yourself
   off the Today/Tomorrow device levels.

## Developing

Structure follows the pattern from
[ffes/domoticz-buienradar](https://github.com/ffes/domoticz-buienradar):

- `fakeDomoticz.py` — simulates enough of the Domoticz plugin framework
  (Devices, Images, Log/Debug/Error) to run `plugin.py`'s
  `onStart()`/`onHeartbeat()` outside Domoticz.
- `testMeteo.py` — a real `unittest` suite (`python3 testMeteo.py`)
  covering CAP-status filtering, the needUpdate fingerprint, multi-day
  span splitting, urgency tagging, all language-mapping fixes, icon key
  lookup, and exact-match region code extraction. Test data uses dates
  relative to when the tests run, not hardcoded dates, so it doesn't go
  stale.

## License

GPL-3.0 — see [`LICENSE`](LICENSE). Same license as the upstream
projects this is forked from.
