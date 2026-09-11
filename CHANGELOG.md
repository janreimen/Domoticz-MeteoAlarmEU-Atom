# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/).

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
- Two related defects found via the same verification, same root cause
  category (embedded literal newlines inside XML attribute values, which
  XML normalizes to a space/leading-space rather than erroring, silently
  corrupting the value): the `Mode1` (`RSSFeed`) default URL had a newline
  splitting `...atom-lux` from `embourg`, and `externallink` had a leading
  newline before `http://`. Both merged onto single lines.
- `getDayIconKey()` never checked `self.iconNo` — selecting **NO_ICON** in
  Mode6 had no effect as long as the icon zip loaded successfully; only
  the plugin-level "did the zip load" flag gated icons, never the user's
  actual setting.

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

