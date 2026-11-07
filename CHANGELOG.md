# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/).

## [1.7.3]

Theme: **community files** - everything GitHub's community profile asks for,
written for this plugin, and tests that keep it from rotting. The plugin
itself behaves exactly as in 1.7.2: no change to devices, texts, defaults or
settings. Planned in `ROADMAP.md`.

### Added
- `CODE_OF_CONDUCT.md`: Contributor Covenant 3.0 (CC BY-SA 4.0, attributed in
  the file). Reporting goes to the maintainer privately through the GitHub
  profile, or to GitHub through *Report content*; there is no placeholder
  address.
- `CONTRIBUTING.md`: bug and feature reporting, setup, project layout, the
  rules that come from earlier mistakes (a plugin problem never looks like a
  weather alert; no renaming devices on update; stable unit numbers; the
  manifest is XML), the three places that hold the version, translations,
  and the release steps.
- `ACCESSIBILITY.md`: what the project controls (device texts, Plugin Status,
  names, documents, forms), what it does, **known limitations** (the level is
  a digit in the text, texts cut at 200 characters, Plugin Status is English
  only, a grey device can keep its last icon, German "no warning" text is
  slang, constructed Luxembourgish words) and what has **not** been checked
  (no assistive-technology testing, no standard claimed).
- Issue forms in `.github/ISSUE_TEMPLATE/`: *Bug report*, *Warning is wrong
  or missing*, *Feature request*, *Accessibility barrier*, and `config.yml`
  with links to the private security report and the troubleshooting table.
  Blank issues stay enabled on purpose, so that a form that is itself a
  barrier does not block anyone.
- `.github/PULL_REQUEST_TEMPLATE.md`: a short checklist that mirrors the
  rules in `CONTRIBUTING.md`.
- `testCommunity.py`: required files exist and contain no template leftovers;
  issue forms are structurally valid (GitHub turns a broken form into a blank
  issue without a message); every relative link and `#anchor` in the
  Markdown documents resolves; headings do not skip levels; images have
  alternative text; link texts say where they lead; the README badge and the
  security policy follow the current version; the layout table in
  `CONTRIBUTING.md` matches the files.
- `requirements-dev.txt` (PyYAML, ruff). CI installs it and now also runs
  `ruff check .`; with `CI` set, a missing PyYAML fails the tests instead of
  skipping the form checks.

### Changed
- `SECURITY.md`: direct link to the private *Report a vulnerability* form, a
  fallback route, and what happens after a report.
- `README.md`: new **Warning levels** table (0 grey, 1 green, 2 yellow,
  3 orange, 4 red, with the CAP severity each comes from), a **Community**
  section, a descriptive alternative text for the screenshot, a version
  badge that links to the changelog (it had an empty link target), and
  descriptive alternative text for the other badges.
- The version is 1.7.3 in the manifest, `PLUGIN_VERSION` and here.

### Not changed, on purpose
- The device text still shows the level as a number (`Wind (3)`), because
  scripts may parse it. Spelling it out is listed as a known limitation in
  `ACCESSIBILITY.md` and as a candidate in `ROADMAP.md`.

## [1.7.2]

Theme: **quiet and safe** - a plugin problem must never look like a weather
alert, a restart must not disturb what the devices show, and a setting that
can never work must not be retried forever. Planned in `ROADMAP.md`.
Upgrading from 1.7.0/1.7.1: see `DEPLOY.md` -> *Upgrading*.

### Changed (behaviour - read before upgrading)
- **A feed problem no longer shows up as a red weather alert.** A failed
  fetch used to set Today/Tomorrow to level 4 (red) with the error text, so
  anything triggered by "level 4" fired on a network blip. Now they keep
  their last values, and once no fetch has succeeded for **3 poll
  intervals** they turn grey (level 0, "No data - feed unreachable since
  HH:MM") until the feed is back. If you relied on the red error state, use
  **Plugin Status** instead.
- **Plugin Status colours**: green = OK, orange = retrying (data still
  fresh), red = failing (data stale) or configuration error, grey =
  starting. Before, OK was level 0 (grey) and ERROR level 1 (green), and
  "OK" was written at start-up before any fetch.
- **Device names are set once and never rewritten on update.** They used to
  be pushed with every update, which overwrote names you had chosen in the
  GUI and broke dzVents/Blockly scripts that reference devices by name. A
  one-time migration at start renames only names the plugin itself
  generated (`Today`, `Today (LU002)`, the 1.7.0 forms `Today: <place>
  (14:05)` / `Heute: ERROR!!!` in any supported language); a name you
  chose is left alone. A name that you give the form `Today (...)` counts as
  plugin-generated and is reset at the next start.
- **The publish time moved from the device name into the device text**:
  `Wind (4) Area 11:00-18:00 [12:00]`, or `[02.11. 12:00]` when the message
  was not published today. It is the newest message for that day.
- **Default polling interval is 30 minutes** (was 300). This applies to
  newly added hardware and as the fallback for an invalid value; an
  existing hardware keeps the value stored in its settings - change it in
  **Setup -> Hardware** if you want 30.
- **Dropdown defaults** are all marked with `selected="selected"` (the
  maintainer's decision). **Debug now defaults to False** - "True" used to
  be the first option and `default="False"` is not an attribute this plugin
  could confirm Domoticz honours. The detail language defaults to
  Luxembourgish, as in the 1.7.1 repo. Defaults only matter for newly added
  hardware.
- `Domoticz.Log` noise: the per-device `BLZ: Awareness Updated/Unchanged`
  lines and `no entry found --> no alert` moved to debug level.

### Fixed
- **Retry storm.** After an error the plugin retried on every 10-second
  heartbeat, ten times, before it first waited (visible in a real log as
  `Error #0 ... #19`). Backoff is now time-based from the first failure:
  1, 2, 5, 10, 30, then 60 minutes, never longer than the poll interval.
  Failures are logged on the first one, when the message changes and while
  the wait escalates; repeats at the longest wait go to debug. A recovery
  is logged once. (`Error #0` also counted from zero.)
- **Settings that can never work are no longer retried.** An empty or
  non-http(s) feed URL, or no region code, is now reported once at start-up,
  Plugin Status turns red with `CONFIG ERROR: ...`, and polling is skipped
  (an empty URL used to produce `unknown url type: ''` every 10 seconds).
  Region codes are cleaned up (comma/semicolon/space separated, upper-cased,
  duplicates removed). A code that does not look like an EMMA_ID (for
  example the old numeric RSS code `202`) or whose country prefix does not
  fit the feed only produces a warning.
- **A non-feed page returned with HTTP 200** (captive portal, error page)
  parsed to zero entries and showed as "no warnings". It is now rejected as
  a fetch error. A real feed with no active warnings is still accepted.
- **Today/Tomorrow are re-split at midnight** from the cached feed, without
  a new request. They were only recomputed after a successful fetch, so
  with a long poll interval "Tomorrow" stayed "Tomorrow" for hours.
- **A restart no longer wipes the devices.** Start-up used to overwrite
  Today/Tomorrow with "No Data", Plugin Status with "OK" and Last Successful
  Update with "never". Only newly created devices get a placeholder, and
  Plugin Status shows "Starting" until the first fetch.
- A region that cannot be processed keeps its previous values and is
  reported on Plugin Status, instead of turning red.
- Publish time in feed-title device names was off by the UTC offset
  (`time.mktime()` on a UTC value); now correct, and shown in the text.
- `meteoalarm_icons.zip` re-packed: the repo copy had a `meteoalarm_icons/`
  folder and 242 macOS `__MACOSX`/`._*` entries, with `icons.txt` not at the
  zip root, which is where Domoticz expects it. The images are unchanged.
  Whether Domoticz refused the old layout is unverified (a successful
  `Create()` is logged either way), but the flat layout is the documented
  one.
- Tests failed whenever they ran within a few hours of midnight (a warning
  "ending in 1 hour" legitimately reached tomorrow). They now use a frozen
  clock.

### Added
- `testManifest.py`: lints the plugin manifest the way Domoticz reads it
  (line scan from `<plugin` to `</plugin>`, parsed as XML) and the icon zip.
  This is the check that would have caught the 1.7.1 `&` bug.
- `testPlugin.py`: end-to-end tests that drive `onStart`/`onHeartbeat` with
  a frozen clock and a scripted feed (status colours, outages and recovery,
  backoff timing, config errors, restart, name migration, midnight, icons).
- `.github/workflows/tests.yml`: runs everything on Python 3.11-3.13.
- `fakeDomoticz.py` now records log lines and device updates and is quiet by
  default (`FAKEDOMOTICZ_VERBOSE=1` prints them).
- `.editorconfig` and a minimal `pyproject.toml` (formatter settings).

### Docs
- README synced with the real settings and device names; `DEPLOY.md` gained
  upgrade notes (plugin key rename, removed `Address` field, poll interval).
- `ROADMAP.md`. The 1.7.1 entry below carries a correction.

### Removed
- `.gitignore` entries `*.1.7.0.md` and `*1.7.0.*` (leftovers of the 1.7.0
  rollback).

## [1.7.1]

### Fixed
- **Root cause of "hardware created but Mode1-6 columns have no value"**: the
  plugin manifest's `externallink` attribute contained a bare, unescaped `&`
  (`...php?f=65&t=19519`). Domoticz extracts the manifest via a plain
  line-by-line text scan of `plugin.py` (confirmed directly from
  `PluginManager.cpp::BuildManifest()` in the Domoticz source - it does
  **not** use Python's `__doc__` or import the module), then parses that
  captured text as XML. A bare `&` is not well-formed XML, so the parse
  failed silently, the "Add Hardware" dialog never received any parameter
  definitions to render, and hardware got created with no Mode1-6/Address
  values ever captured. Fixed by escaping it as `&amp;t=19519`, per the XML
  spec. Verified by reproducing Domoticz's exact extraction+parse algorithm
  against the real file - confirmed broken before, confirmed clean after.
- **Correction (added in 1.7.2):** this entry originally listed two more
  defects, "embedded literal newlines" in the `Mode1` default URL and in
  `externallink`. That was wrong. The line breaks were terminal wrapping in
  the `more` output that had been pasted for diagnosis: in each paste the
  broken line was exactly as wide as the terminal (145 and 188 characters),
  and a real newline would not break at the terminal width. The bare `&`
  above is the only root cause; nothing needed merging.
- `getDayIconKey()` never checked `self.iconNo` — selecting **NO_ICON** in
  Mode6 had no effect as long as the icon zip loaded successfully; only
  the plugin-level "did the zip load" flag gated icons, never the user's
  actual setting.

### Changed (documented retroactively in 1.7.2 - these were in the 1.7.1 code but not in this file)
- **The `Address` hardware field was removed.** All region codes now go in
  **RSSCode(s)** (`Mode2`) as a comma-separated list, default
  `LU002, LU001`; the first code keeps Units 1/2, further codes get Units
  5/6, 7/8, ... Extra regions that were entered in `Address` under 1.7.0
  are no longer read - re-enter them in `Mode2`.
- **Region code in every Today/Tomorrow device name**, including the first
  region (`Today (LU002)`, `Tomorrow (LU002)`); existing devices were
  renamed at start-up, and feed-generated titles no longer overwrote the
  names. (1.7.2 reworked this: names are set once, see below.)

### Added
- Luxembourgish as a 7th detail-language option ("Detailer op
  Lëtzebuergesch"). Most terms verified against official MeteoLux
  documents and the LOD dictionary; *Coastal Event* and *Avalanches* are
  constructed (no native precedent — neither is a real Luxembourg weather
  phenomenon) and worth a native-speaker sanity check.
- `LICENSE` (GPL-3.0 — required, since the upstream project this is
  forked from is GPL-3.0 licensed), `SECURITY.md`, `DEPLOY.md`.
- This `CHANGELOG.md`, replacing the growing prose changelog duplicated
  across `plugin.py`'s docstring and the README.

### Removed
- Dead code found during cleanup: unused imports (`datetime as dt`,
  `json`, `re`, `math.*`, `os.path` in `plugin.py`), unused `Meteo`
  attributes (`.debug`, `.error`, `.nextpoll`, `.observationDate`),
  unused `parseIntValue()`/`parseFloatValue()` helpers, a stray
  `fritzHelper.py` reference (leftover from an unrelated project,
  present in the upstream README too).

### Docs
- README rewritten for clarity and reorganized around the new
  `DEPLOY.md`/`SECURITY.md` split.

## [1.7.0]

### Changed (documented retroactively in 1.7.2)
- **The plugin `key` changed from `MeteoAlarmEU Atom` to `MeteoAlarmEU-Atom`**
  (visible in git: 1.6.x tags use the old key, `v1.7.0` the new one). Domoticz
  stores the key with each hardware, so a hardware added under 1.6.x is
  tied to the old key. See `DEPLOY.md` -> *Upgrading from 1.6.x* for how to
  check and fix it.

### Added
- **Multi-region support**: the previously-unused `Address` hardware
  field now accepts comma-separated additional region codes, each
  getting its own Today/Tomorrow device pair. All regions share a single
  feed fetch per heartbeat instead of each fetching independently.
- Bundled severity+type icon set (12 warning categories × meteoalarm's
  4-colour scale), replacing the icons the feed itself no longer
  provides. **Built against documented Domoticz conventions but not
  verified against a live instance** — falls back to the default Alert
  icon on any load failure.
- `cap:status` filtering — only `Actual` alerts are shown; `Test`,
  `Exercise`, `Draft`, and `System` CAP messages are now excluded.
- `cap:urgency` surfaced as `[upcoming]`/`[ending]` in verbose detail mode.
- `testMeteo.py`, a real `unittest` suite, and a fuller `fakeDomoticz.py`
  that simulates device/image creation for end-to-end testing.

### Fixed
- `DOM_LANG_TO_METEO['se']` → `'sv'` — Domoticz's actual Swedish language
  code; `'se'` never matched anything, silently disabling Swedish
  detail-language auto-detection.
- `needUpdate` is now a real before/after fingerprint of the rendered
  text, replacing an unreliable `pubDate`-based proxy.

## [1.6.3]

### Changed
- **Parser rewritten against the real, live CAP-Atom feed structure**
  (verified by fetching it directly). The previous code assumed an HTML
  table with icons and per-language text embedded in each entry's
  `<description>` — the feed no longer provides that at all, so every
  matching entry against real data would throw `KeyError`. Parsing now
  reads `cap:event`/`cap:severity`/`cap:onset`/`cap:expires` directly.
- Multi-day warning spans now correctly appear in both Today and
  Tomorrow using real timestamps, instead of losing the date once
  "today" no longer applied.

### Fixed
- German/Swedish detail-language selection silently fell back to
  English (`getLangIndex` was checking for the native-language words
  instead of the English names actually in use).

### Removed
- `beautifulsoup4` and `python-dateutil` dependencies — no longer
  needed; only `feedparser` is required.

## [1.6.2]

### Added
- **Plugin Status** and **Last Successful Update** devices.
- Exponential error backoff (10 → 20 → 40 → 80, capped at 120 minutes),
  replacing a flat 10-minute retry.
- Startup sanity check on the configured feed URL.

### Fixed
- Multi-day warning spans now show a date + day-offset (e.g. `+1d`)
  instead of silently dropping the date.

## [1.6.1]

### Fixed
- `AttributeError: 'BasePlugin' object has no attribute 'mt'` crash-loop
  in `onHeartbeat()`, caused by `onStart()` failing part-way through
  (an `UnboundLocalError` in `getMeteoLang()` on an unmapped Domoticz
  language, or a missing `pollinterval` fallback on an invalid Update
  setting) before `self.mt` was ever assigned.
- Inverted error-backoff condition (`if self.errorCounter % 10:` fired on
  every count *except* multiples of 10 — the opposite of intended).
- `mktime(None)` crash showing the device title when a feed poll
  returned zero matching entries.

## [1.6.0]

### Changed
- Switched from RSS to Atom feeds, following meteoalarm.org's own
  migration (legacy RSS feeds were sunset).

## [1.0.0] – [1.5.0]

Original `belze`/`ycahome` plugin: initial version through bug fixes,
BeautifulSoup-based RSS parsing, detail/language/icon options, and a
class-based rewrite. See git history for details predating this file.

