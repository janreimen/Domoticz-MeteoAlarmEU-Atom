# Roadmap

Review of **Domoticz-MeteoAlarmEU-Atom 1.7.1** (written 2026-11-01), the
scope of **1.7.2** that came out of it (built 2026-11-02 to 2026-11-06), and a
backlog for 1.8.x and later.

**Status:** 1.7.2 is built; every item marked *Done* below is in the code and
covered by tests (see `CHANGELOG.md` for the user-facing description). Section
5 records the decisions taken, section 6 what is still open.

## How to read this

Every finding carries an evidence tag, so you can tell what was seen from what
is assumed:

| Tag | Meaning |
| --- | --- |
| `[log]` | Seen in the `journalctl` paste of 2026-09-11 |
| `[code]` | Read in the 1.7.1 `plugin.py` / `meteo.py` / `testMeteo.py`; line numbers refer to the 1.7.1 files |
| `[paste]` | Seen in the `more plugin.py` paste taken on the Pi |
| `[repo]` | Seen on the live GitHub repo pages |
| `[unverified]` | Plausible but not confirmed; says what would confirm it |

Effort: **S** under an hour, **M** about half a day, **L** more than a day.
Risk is the chance that the change alters behaviour users rely on.

**Base of the findings.** The first version of this roadmap was written from
the 1.7.1 files I had delivered earlier, because the live `plugin.py` could not
be fetched. Before building 1.7.2 the live repo was cloned (master `b4d756b`,
tag `v1.7.1`) and compared: `meteo.py`, `testMeteo.py`, `README.md`,
`DEPLOY.md` and `SECURITY.md` were identical to my copies; `plugin.py` differed
(vertical reformatting, `Mode2` as a comma-separated list, region-qualified
device names). Each finding below was re-checked against the live `plugin.py`;
where the live code differs, section 0 and the finding say so.

---

## 0. Corrections to earlier documents

**C1. The 1.7.1 CHANGELOG blames embedded newlines; they were display wrapping.**
`CHANGELOG.md` says the `Mode1` default URL and `externallink` contained
literal newlines. The evidence says otherwise:

- In the older uploads the widest line is exactly 145 characters, and that is
  the line broken at `atom-lux` / `embourg`.
- In the Pi paste the widest line is exactly 188 characters, and that is the
  line broken at `viewtopic.php` / `?f=65`.

A line that breaks exactly at the widest width in each paste is terminal
wrapping in `more`, not a real newline. The real root cause of the empty
hardware fields is the bare `&` in `externallink`, which made the manifest
invalid XML; fixing it to `&amp;` was the right change. **Action:** reword the
CHANGELOG entry (in 1.7.2). To confirm on the Pi:
`grep -n 'atom-lux$' plugin.py` should return nothing.

**C2. `LICENSE` in the delivered files has no GPL text.** The repo now
detects GPL-3.0 `[repo]`, so this is resolved there; do not re-upload the
delivered copy.

**C3. The plugin `key` changed in 1.7.0, not 1.7.1.** An earlier version of this
file said the key was renamed in 1.7.1. The git history shows `MeteoAlarmEU
Atom` (with a space) in the 1.6.x tags and `MeteoAlarmEU-Atom` from `v1.7.0`
on. What changed in 1.7.1 is the removal of the `Address` field (all regions
now go in `Mode2`) and the region code in every device name. None of the three
was in `CHANGELOG.md`; they are documented there now, and `DEPLOY.md` has
upgrade notes for 1.6.x and for 1.7.0/1.7.1.

**C4. B8 looked different in the live code.** The live 1.7.1 already built
device names from the region code (`Today (LU002)`) instead of from the feed
title, so the name no longer carried the publish time. Two defects remained:
the name was still pushed with every update (overwriting names chosen in the
GUI), and the publish time, which the live manifest still advertised ("shown
in device value"), was shown nowhere because the title function was no longer
called. Both are fixed in 1.7.2 (B8).

**C5. A suspicion that did not hold up.** I had suspected that the `v1.7.1` tag
pointed at a commit outside master. It is an annotated tag; the commit behind it
is `b4d756b`, master's head. Nothing to do.

---

## 1. Scope of 1.7.2: "quiet and safe" (built)

Theme: the plugin must never turn a *problem* into a *weather alert*, must
never report a false all-clear, and should stop retrying things that cannot
succeed. Plus the tests and docs that would have caught the 1.7.0/1.7.1
regressions.

Status key: **Done** = in 1.7.2 and covered by tests. The end-to-end tests
were mutation-checked: ten deliberate bugs (errors painting red, no midnight
rollover, renaming custom names, late staleness, retry on every heartbeat,
inverted status colour, wiping at start, polling on a config error, grey
sticking after recovery, renaming on update) were each caught by at least one
test; two escaped at first, which exposed weak tests that were then fixed.

### Behaviour

| ID | Item | Evidence | Effort | Risk | Status |
| --- | --- | --- | --- | --- | --- |
| B1 | Plugin Status colours are inverted, and Status says "OK" before any fetch | `[code]` | S | low | Done |
| B2 | A feed error paints Today/Tomorrow **red** (level 4) | `[code]` | S | med | Done |
| B3 | Empty/invalid config is retried forever as if it were a network error | `[log]` | S | low | Done |
| B4 | Backoff retries 10 times every 10 s before it waits; log spam | `[log]` `[code]` | S | low | Done |
| B5 | Garbage that returns HTTP 200 parses as "all clear" | `[code]` | S | low | Done |
| B6 | Today/Tomorrow are not re-evaluated at midnight | `[code]` | S–M | low | Done |
| B7 | Start-up overwrites Today/Tomorrow and Status | `[code]` `[repo]` | S | low | Done |
| B8 | Device names are rewritten on every update | `[code]` | S | **high** | Done (decided) |
| B9 | `BLZ:` messages are logged at info level on every poll | `[code]` | S | none | Done |
| B10 | A wrong region code silently shows "no warning" | `[code]` | S | low | Done (warns only) |

### Tests, docs, repo

| ID | Item | Evidence | Effort | Risk | Status |
| --- | --- | --- | --- | --- | --- |
| T1 | Manifest-lint test (catches the `&` class of bug) | `[log]` history | S | none | Done |
| T2 | Commit an end-to-end test that drives `onStart`/`onHeartbeat` | `[code]` | M | none | Done |
| T3 | GitHub Actions CI (Python 3.11–3.13) | `[repo]` no `.github/` | S | none | Done |
| D1 | Sync README with the live manifest and device names | `[repo]` | S | none | Done |
| D2 | Upgrade notes: plugin-key rename, removed `Address` field | `[repo]` | S | none | Done |
| D3 | Correct the CHANGELOG newline claim (C1) | C1 | S | none | Done |
| D4 | Manifest defaults: `default` vs `selected`, stale `default="202"` | `[paste]` | S | low | Done (decided) |
| E1 | Repo hygiene (`.gitignore`, formatter config, description/topics, Release) | `[repo]` | S | none | Partly: repo files done; Release, description and topics need your GitHub account |


---

## 2. Findings in detail

### B1. Plugin Status colours are inverted
`[code]` `plugin.py:265, 319, 339`

The Plugin Status device is an Alert device. Alert levels are 0 grey, 1 green,
2 yellow, 3 orange, 4 red. The plugin writes `updateDevice(3, 0, "OK")` and
`updateDevice(3, 1, "ERROR #n: …")`, so **OK shows grey and ERROR shows green**.
On start-up it also writes `"OK"` before any fetch has happened.

*Fix:* starting = grey, OK = green, retrying = orange, failing or config error
= red. Write nothing "OK" until the first successful fetch.
*How to confirm first:* look at the Plugin Status device in the GUI during a
forced error.

### B2. Feed errors look like red weather alerts
`[code]` `plugin.py:314-318, 350-352`

When the fetch fails, Today and Tomorrow are set to **level 4** with the
error text as the value. Any notification or automation triggered by "level 4"
fires on a network blip. In `[log]` the `Error #n on reading feed` lines come
from this same branch, so the empty-URL failure ran through it on every retry.

*Fix (stale-while-error):* keep the last known Today/Tomorrow values on error
and let Plugin Status carry the failure. After a staleness limit (for example
three poll intervals) set Today/Tomorrow to grey (level 0) with the text
"stale", so an old all-clear never lingers for days.
*Risk:* anyone who relied on the red error state needs to switch to Plugin
Status. Worth a line in the CHANGELOG.

### B3. Config errors are retried like transient errors
`[log]` journalctl lines 11-39

With an empty `Mode1` the plugin logged `Invalid polling interval parameter ''`
and `Configured RSSFeed URL '' does not look like…`, then **kept fetching**:
`Error #0 … #19` every 10 s, with `unknown url type: ''` each time.

*Fix:* validate once in `onStart`: non-empty `http(s)` URL; interval is an
integer; every region code matches `^[A-Z]{2}\d{3}$` after trimming and
upper-casing; the code's country prefix is plausible for the feed. On failure:
log **one** clear error, set Plugin Status to red "config error", and do not
poll at all.

### B4. Backoff retries ten times before it waits
`[log]` lines 13-39, `[code]` `plugin.py:154-155, 310-331`

`nextpoll` is only pushed out when `errorCounter % 10 == 0`. For the nine
errors in between, `nextpoll = now`, so the plugin retries on **every
heartbeat (about 10 s)**. The log shows exactly this: ten errors 10 s apart,
a 10-minute wait, ten more errors, a 20-minute wait. A genuinely down feed
gets 10 requests in under two minutes each cycle.

Smaller issues in the same block:

- The first error is logged as `Error #0` (the counter is read before it is
  incremented).
- The wait steps are labelled minutes but only apply after ten failures.

*Fix:* time-based backoff from the first failure (for example 1, 2, 5, 10, 30,
60 minutes), one log line per state change (first failure, each backoff step,
recovery) rather than one per attempt.

### B5. HTTP 200 with garbage parses as "all clear"
`[code]` `meteo.py:84-88`

`feedparser` does not raise on bad input. A captive-portal page or an error
page served with status 200 sets `bozo`, which is only logged at debug level,
then yields **zero entries**, which the plugin reads as "no warnings". The
same blind spot sits behind B10.

*Fix:* if `bozo` is set and the parsed feed has no feed-level title or
updated time, raise a fetch error instead of processing it.
`[unverified]` that every real MeteoAlarm response carries a feed title; a
saved real response would confirm it (see F2).

### B6. Today/Tomorrow are not recomputed at midnight
`[code]` `plugin.py:301, 345` and `meteo.py` `processFetchedFeed`

`processFetchedFeed` is only called after a successful fetch, and
`onHeartbeat` returns early until `nextpoll`. The default interval is
**300 minutes** (`default="300"`, `DEFAULT_POLL_MINUTES = 300`). After midnight
"Tomorrow" is really "Today", but the devices keep the pre-midnight values for
up to five hours.

*Fix (cheap):* keep the last parsed feed in memory and, on the first
heartbeat after the local date changes, call `processFetchedFeed` on the
cached feed. No extra network request. Also see decision Q4 on the default
interval.

### B7. Start-up overwrites state
`[code]` `plugin.py:263-266`, `[repo]`

`onStart` writes level 0 "No Data" to Today/Tomorrow and, with
`alwaysUpdate=True`, resets Plugin Status to "OK" and Last Successful Update to
"never". `nextpoll` starts at "now", so the first heartbeat refetches within
seconds and the visible damage is short, but every restart still produces a
state flip that automations can see, and the last-update timestamp is lost.

*Fix:* only create missing devices; leave existing values alone until the first
real result.

### B8. Device names are rewritten on every update
`[code]` `meteo.py:188-201`, `plugin.py:487-491`

Each update passes `Name=…`, and the name is built from the publish time, for
example `Today: Luxembourg (14:05)`. So:

- the name changes whenever a newer message arrives;
- the error path renames the device to `Today: ERROR!!!`;
- a name the user chose in the GUI is overwritten on the next update;
- dzVents, Blockly and scripts that reference devices **by name** break.

The publish time is a deliberate feature (`Meteo.SHOW_DATE_IN_NAME = True`,
hard-coded, `meteo.py:95`), so removing it is a product decision, not a bug
fix. *Decision (section 5, Q2): stable names, publish time moved into the
device text. Note C4: the live code differed slightly.* **Done in 1.7.2:**
names are set once (creation, plus a one-time migration at start for names the
plugin generated itself), updates never pass a name, and the text ends with
`[HH:MM]`.

### B9. Log noise
`[code]` `plugin.py:492, 494`

`Domoticz.Log("BLZ: Awareness Updated …")` and `"BLZ: Awareness Remains
Unchanged"` run at info level for every device on every poll. Move both to
`Domoticz.Debug` and drop the upstream "BLZ" prefix.

### B10. A wrong region code looks like good news
`[code]` `testMeteo.py:160` (the test asserts this behaviour)

MeteoAlarm lists only *active* warnings, so a typo such as `LU01` is
indistinguishable from "no warning today", and the plugin shows green. The
feed cannot validate a code, so the realistic fix is B3's format and country
check plus a one-time warning in the log, not a hard failure.

### T1. Manifest-lint test
`[log]` history

Domoticz builds the settings form by scanning `plugin.py` from `<plugin` to
`</plugin>` and parsing that text as XML (`PluginManager.cpp`,
`BuildManifest`). One bad character produces an empty settings form and empty
Hardware columns, which is exactly what 1.7.1 fixed.

*Test:* extract the same block, parse it with `xml.etree`, and assert: it is
well-formed; `key` is unique and has no spaces; every `<param>` has a
`field`; every dropdown has exactly one default; option values are unique;
the `version` attribute matches `PLUGIN_VERSION` and the top of `CHANGELOG.md`.

### T2. Committed end-to-end test
`[code]` `fakeDomoticz.py` exists

An ad-hoc harness of this kind caught the icon-name case bug earlier, but it
was never committed. Add `testPlugin.py` that drives `onStart`/`onHeartbeat`
with `meteo.fetchFeed` monkeypatched, covering: first fetch, error path (B1,
B2), recovery, backoff timing (B4), config validation (B3), restart with
existing devices (B7), midnight rollover with a fake clock (B6), and multi-region
unit allocation.

### T3. CI
`[repo]` no `.github/` directory

One workflow: checkout, set up Python 3.11 / 3.12 / 3.13, install
`requirements.txt`, run `python -m py_compile`, `python -m unittest`, and the
manifest lint. Fails the PR on any error.

### D1–D3. Docs
- **D1.** The README describes the older `Address` field and `Today` /
  `Tomorrow` device names `[repo]`; the live plugin uses a comma-separated
  `Mode2` and `Today (<code>)`. The screenshot is hot-linked from
  `belzetrigger/domoticz-MeteoAlarmEU` `[code]` `README.md:10`, so it shows the
  upstream UI and depends on someone else's repo; replace it with a local
  screenshot of this plugin.
- **D2.** `DEPLOY.md` needs upgrade notes (see C3): the plugin `key` changed in
  1.7.0 from `MeteoAlarmEU Atom` to `MeteoAlarmEU-Atom` `[repo]`, and a hardware
  row stores the key with it. `[unverified]` how Domoticz treats a row whose
  key no longer matches, so the notes say what to check and what to do (re-add
  the hardware) rather than what will happen. The `Address` field was removed
  in 1.7.1, so extra regions configured there are silently dropped; they must
  be re-entered in `Mode2`. **Done** (sections *Upgrading from 1.7.0 / 1.7.1 to
  1.7.2* and *Upgrading from 1.6.x*).
- **D3.** Reword the newline claim (C1).

### D4. Manifest defaults
`[paste]` manifest lines 96, 101, 107, 121

- `Mode4` marks its default with `default="False"`, `Mode5`/`Mode6` with
  `selected="selected"`. The attribute Domoticz honours for a dropdown default
  is `[unverified]`: the Domoticz wiki was not reachable from this session, and
  two community plugins checked did not show a manifest. I recall
  `default="true"`. If `selected` is ignored, Mode5/6 still work by luck
  (their first option is the intended default), but Mode4's first option is
  **Debug**, so a freshly added hardware would start with debug logging on.
  *Test:* add a fresh hardware and look at the Debug dropdown.
- **Resolution (decision, section 5):** every dropdown marks its default with
  `selected="selected"`, Debug's first option is now `False`, and
  `testManifest.py` enforces exactly one `selected` per dropdown and no
  `default=` on an option. Whether Domoticz honours `selected` is still
  `[unverified]` (see section 6, question 1).
- `Mode2` carries `default="202"`, a leftover from the RSS era. The live repo
  already changed it to `LU002, LU001` `[repo]`; the new default includes two
  regions, so confirm that is intended.

### E1. Repo hygiene
`[repo]`

- `.gitignore` contains `*.1.7.0.md` and `*1.7.0.*`, which look like leftovers
  from the 1.7.0 rollback (removed in 1.7.2). `settings.json` sits under the
  "VS Code" heading and is fine; an earlier version of this file wrongly listed
  it as a leftover.
- `externallink` is a clone URL ending in `.git` on `www.github.com`; use the
  plain web URL.
- `primaryCode` is assigned but unused, and comments still mention `Address`.
- No formatter config. The live `plugin.py` was reformatted vertically
  (1016 lines against about 365), so diffs against the old layout are noisy;
  pick a formatter (for example `ruff format`) and commit its config so this
  happens once.
- Publish a GitHub Release for `v1.7.1`. The tag exists (see C5); whether a
  Release exists is `[unverified]` (GitHub release pages were not fetchable).
- Repository description and topics (`domoticz`, `domoticz-plugin`,
  `meteoalarm`, `weather-warnings`).

**Done in 1.7.2:** `.gitignore`, `externallink`, unused `primaryCode` and the
`Address` comments (the whole start-up code was rewritten), `.editorconfig`,
`pyproject.toml` (ruff settings; `ruff check` is clean, the one-time `ruff
format .` is left for a commit of its own). **Needs you:** the GitHub Release,
description and topics (commands in section 6).

### New findings while building 1.7.2

- **Z1. The icon zip in the repo was packed with a subfolder and macOS
  leftovers.** `[repo]` `meteoalarm_icons.zip` had everything inside a
  `meteoalarm_icons/` folder, `icons.txt` not at the zip root, and 242
  `__MACOSX/._*` entries (484 entries instead of 241). The images themselves
  were byte-identical to my flat zip. Domoticz documents `icons.txt` at the
  root; whether it refused the old layout is `[unverified]`, and a successful
  `Create()` is logged either way, so nothing in the logs would have told.
  **Done:** repacked flat; `testManifest.py` checks the layout and the five
  files per icon; the fake Domoticz now requires `icons.txt` at the root; a
  Debug line shows whether the icons registered.
- **Z2. A test already failed on live HEAD** (`test_warning_ending_today_does_not_appear_tomorrow`).
  The suite built its data from the real time of day, so within a few hours of
  midnight a warning "ending in 1 hour" legitimately reaches tomorrow. It
  surfaced because this session ran at about 23:40. **Done:** frozen clock.
- **Z3. The publish time was shown in UTC, labelled as local.** `meteo.py` used
  `time.mktime()` on feedparser's UTC value; `calendar.timegm()` is correct.
  Only visible in the old title-based names. **Done**, with a test in a
  non-UTC time zone.
- **Z4. feedparser tells a feed from a web page by `version`.** For non-feeds
  (HTML, JSON, plain text) it reports an empty `version`; for a real Atom feed
  `atom10`, also when there are zero entries. My first version of the B5 guard
  looked at feed-level fields instead and let an HTML page through (found by
  its own test). The guard now rejects only when the format is unrecognised
  **and** no `title`/`id`/`updated` exists, so it cannot refuse a real feed.
  `[unverified]` against the live MeteoAlarm document, which this sandbox could
  not fetch: `DEPLOY.md` has a one-line check to run on the Pi.
- **Z5. A grey (stale) device keeps its previous warning icon.** Known
  limitation, documented in the README; see the backlog.

---

## 3. Backlog for 1.8.x

| ID | Item | Why | Effort | Notes |
| --- | --- | --- | --- | --- |
| F1 | Classify with the CAP `awareness_type` / `awareness_level` parameters instead of title keywords | More robust than string matching | M | `[unverified]` that Atom entries expose them; inspect a saved real entry first |
| F2 | Real-feed fixtures in `tests/fixtures/` plus `tools/make_fixture.py` | 8 of 12 warning categories are only tested with synthetic data | M | Fetching must happen on your Pi; this sandbox cannot reach the feed |
| F3 | Conditional GET (`ETag` / `If-Modified-Since`) | Fewer requests, politer to the feed | S | `[unverified]` that the feed sends validators |
| F4 | Response size cap and explicit response close | `response.read()` is unbounded and the response is never closed (`meteo.py:71-73`) | S | Hardening |
| F5 | Catch broader network exceptions in `fetchFeed` | `ConnectionResetError`, `IncompleteRead` and other `OSError`s escape with raw messages | S | |
| F6 | Italian, Dutch, Portuguese, Polish detail languages; move translations to a JSON file | Community-maintainable | M | Native check still wanted for the two constructed Luxembourgish terms (Coastal Event, Avalanches) |
| F7 | Multiple countries in one hardware | Today needs one hardware per country (you already run two: Luxembourg and Italy) | L | Needs per-region feed URL and per-region time zone (see L2) |
| F8 | Surface `cap:certainty` and `message_type` (Alert vs Update) | Fetched but not shown | S | |
| F9 | Optional "full text" device with the complete warning text | `MAX_SHOWN_DETAIL_LENGTH = 200` truncates | S | |
| F10 | dzVents / Blockly examples in `docs/` | The README's idea list asks for automations | S | |

### Added to the backlog while building 1.7.2

| ID | Item | Notes |
| --- | --- | --- |
| F11 | Reset the icon when Today/Tomorrow go grey | Needs the default image id for an Alert device, `[unverified]` |
| F12 | Run `ruff format .` once, in a commit of its own | Config is in `pyproject.toml`; keeps later diffs readable |
| F13 | Check the guard and the parser against a saved real feed | Same fixtures as F2 |

## 4. Later / ideas

- **L1.** Python Plugin Store metadata and a release channel, once the plugin key
  is final.
- **L2.** Time zone handling: day boundaries use the Pi's local time
  (`datetime.now().astimezone()`), which is right for Luxembourg and wrong for
  a feed in another zone.
- **L3.** Dependabot and `pip-audit` for `feedparser`.
- **L4.** A `file://` fixture mode to verify icon rendering without the network.
- **L5.** Hysteresis or "next change at" text so a warning ending in an hour is
  visible.

---

## 5. Decisions taken

Answers given 2026-11-02:

| # | Question | Decision |
| --- | --- | --- |
| Q1 | Whole set in one release? | Not answered explicitly; built as one release |
| Q2 | Device names (B8) | Stable names; publish time moved into the device text |
| Q3 | Error display (B2) | Keep last values, grey after three poll intervals |
| Q4 | Default poll interval | 30 minutes (new hardware only) |
| Q5 | Default regions | Keep `LU002, LU001` |
| Q6 | Dropdown defaults (D4) | `selected="selected"` everywhere |

One default was taken from the live repo rather than decided: the detail
language defaults to **Luxembourgish** (`Mode5`), because the 1.7.1 manifest
tried to mark it (with a wrong attribute value). Say so if a neutral default
such as `NO_DETAIL` is preferred for other users of the plugin.

## 6. Open questions

1. **Does Domoticz honour `selected="selected"`?** Add a fresh hardware once:
   the Debug dropdown should show *False*, Details *Luxembourgish*, icons
   *NO_ICON*. This is the verification that was asked for in Q6 and is still
   needed; the lint test only checks the manifest, not Domoticz.
2. **Is your hardware tied to the old key?** Under 1.6.x the key was
   `MeteoAlarmEU Atom`. On the Pi:
   `sqlite3 domoticz.db "SELECT ID, Name, Extra, Mode1, Mode2, Mode3 FROM Hardware WHERE Extra LIKE 'MeteoAlarmEU%';"`
   and compare `Extra` with `MeteoAlarmEU-Atom`. If a row differs, that may
   relate to the earlier "hardware 54 loses its settings" report, but that link
   is a hypothesis, not a finding.
3. **Existing hardware keeps `Update every x minutes` = 300.** Change it to 30
   in the GUI; the new default only applies to newly added hardware.
4. **Does the guard accept the live feed?** Run the one-liner in `DEPLOY.md`
   (*Verifying*, step 0); expect `atom10` and a `title`.
5. **Do the icons show up** with *inline icon* selected, now that the zip is
   packed flat? Look for `Custom severity/type icon set loaded` and, in Debug,
   `Icon probe ... registered in Images: True`.
6. **GitHub housekeeping that needs your account:** a Release for `v1.7.2`
   (and `v1.7.1` if none exists), description and topics, for example
   `gh release create v1.7.2 --title "1.7.2 - quiet and safe" --notes "See CHANGELOG.md, section 1.7.2"`
   and `gh repo edit --description "Domoticz plugin: MeteoAlarm.org weather warnings from the CAP-Atom feed" --add-topic domoticz --add-topic domoticz-plugin --add-topic meteoalarm`.
7. **Plugin Store `git@github.com: Permission denied (publickey)`** appears four
   times in `[log]` lines 20-23. The messages do not name a plugin, so I cannot
   attribute them to this one; `DEPLOY.md` now tells to use the HTTPS URL.
