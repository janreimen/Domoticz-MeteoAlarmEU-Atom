# Deployment Guide

Step-by-step install/upgrade instructions for `Domoticz-MeteoAlarmEU-Atom`.
For what the plugin does and how it works internally, see `README.md`.

## Prerequisites

- A running Domoticz install (tested with 4.10038 and 2026.1)
- Python 3.13
- The `feedparser` Python package (only dependency as of 1.6.3+)

## Fresh Install

1. **Install the Python dependency:**
   ```bash
   sudo pip3 install -r requirements.txt --break-system-packages
   ```
   (drop `--break-system-packages` on older Python/pip where it's not
   needed or not recognized)

2. **Clone into your Domoticz plugins directory:**
   ```bash
   cd domoticz/plugins
   git clone https://github.com/janreimen/Domoticz-MeteoAlarmEU-Atom.git
   ```
   Or download and unzip the release archive into `domoticz/plugins/`
   instead, if you're not using git.

   Always use the **HTTPS** URL. An SSH remote (`git@github.com:...`)
   needs a deploy key for the user Domoticz runs as; without one, the
   Python Plugin Store logs `Git Fetch Error: git@github.com: Permission
   denied (publickey)` for it.

3. **Place the icon zip alongside `plugin.py`:**
   `meteoalarm_icons.zip` must sit directly in the same folder as
   `plugin.py` — Domoticz resolves it via the plugin's own `HomeFolder`.
   If you cloned via git and the zip is tracked in the repo, this step
   is already done; otherwise copy it in manually.

4. **Windows / Synology only:** make sure the installed Python modules
   are on the interpreter's path (site-packages). If not, add the path
   near the top of `plugin.py` — see the comment there for where.

5. **Restart the Domoticz service:**
   ```bash
   sudo systemctl restart domoticz.service
   ```

6. **Add the hardware:** Domoticz UI → **Setup → Hardware** → add
   **Meteo Alarm EU RSS Reader Atom**.

7. **Configure it** — see `README.md` → *Settings* for what each field
   means (feed URL, region code(s), language, icons). The feed URL and the
   region code(s) must belong to the same country, for example
   `...legacy-atom-luxembourg` with `LU002, LU001`. If either is empty,
   Plugin Status turns red with `CONFIG ERROR: ...` and nothing is polled
   until you fix it.

## Upgrading an Existing Install

1. **Back up first** — your existing `plugin.py`/`meteo.py` and any
   local modifications:
   ```bash
   cd /srv/domoticz/plugins/Domoticz-MeteoAlarmEU-Atom
   cp plugin.py plugin.py.bak
   cp meteo.py meteo.py.bak
   ```

2. **Pull or copy in the new files.** If using git:
   ```bash
   git pull origin master
   ```

3. **Restart Domoticz:**
   ```bash
   sudo systemctl restart domoticz.service
   ```

4. **Device IDs are stable across upgrades** — the first region always
   keeps Units 1 (Today) and 2 (Tomorrow), so existing dashboards/
   automations tied to those devices keep working after an upgrade.
   Additional-region devices and the Plugin Status/Last Successful Update
   devices (Units 3/4) are created automatically on first start if they
   don't already exist.

5. **If you were on a pre-1.6.3 version:** the feed format itself
   changed upstream (meteoalarm.org sunset legacy RSS), and the parser
   was rewritten to match. There's nothing you need to do differently,
   but expect device text formatting to look different after upgrading,
   since the whole parsing approach changed with it.

### Upgrading from 1.7.0 / 1.7.1 to 1.7.2

Read these before you restart - 1.7.2 changes what the devices show:

- **A feed problem no longer turns Today/Tomorrow red.** They keep their
  last values and turn **grey** after three poll intervals without a good
  fetch. Plugin Status carries the failure: green OK, orange retrying, red
  failing or configuration error, grey starting. If an automation
  triggers on "Today = level 4" to detect *errors*, move it to Plugin
  Status (level 4 = red).
- **The publish time is now at the end of the device text** (`[12:00]`),
  not in the device name. Names are stable: `Today (LU002)` etc. The first
  start after the upgrade renames devices that still carry an old
  plugin-generated name (`Today`, `Today: Luxembourg (14:05)`, ...) once.
  A name you chose yourself is kept. Avoid giving a device a name of the
  form `Today (...)`, which counts as plugin-generated.
- **The default polling interval is now 30 minutes, but only for newly
  added hardware.** Your existing hardware keeps its stored value (the
  old default was 300 minutes, five hours): open **Setup → Hardware**,
  change **Update every x minutes** to `30`, and press **Update**.
- **The `Address` field no longer exists (since 1.7.1).** If you entered
  extra regions there under 1.7.0, they are not read any more: put all
  codes in **RSSCode(s)**, comma-separated, first = the region on Units
  1/2.
- **Debug now defaults to False** for newly added hardware; an existing
  hardware keeps its setting.

### Upgrading from 1.6.x

Since 1.7.0 the plugin's internal `key` is `MeteoAlarmEU-Atom` (it was
`MeteoAlarmEU Atom`, with a space). Domoticz stores the key with each
hardware, so a hardware that was added under 1.6.x may no longer be
matched to the plugin. Check it (stop Domoticz or work on a copy of the
database first; the path depends on your install):

```bash
sqlite3 domoticz.db "SELECT ID, Name, Extra FROM Hardware WHERE Extra LIKE 'MeteoAlarmEU%';"
```

If `Extra` shows `MeteoAlarmEU Atom` for your hardware, the simplest and
safest fix is to delete that hardware in **Setup → Hardware** and add it
again (its devices are re-created; dashboards and scripts that point at
the old devices need re-pointing). I have not been able to verify what
Domoticz does with a row whose key no longer matches, so treat the SQL
route (`UPDATE Hardware SET Extra='MeteoAlarmEU-Atom' WHERE ...`) as
something to try only after a database backup.

## Verifying It's Running Correctly

0. **Optional, before the first start of 1.7.2** — confirm that the feed you
   use is recognised as an Atom feed by the same library the plugin uses
   (1.7.2 refuses a response that is not a feed instead of showing "no
   warnings"):
   ```bash
   python3 -c "import feedparser; f = feedparser.parse('https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-luxembourg'); print(f.version, len(f.entries), sorted(f.feed))"
   ```
   Expect `atom10`, the number of active warnings (0 is fine) and a list of
   feed-level fields that includes `title`. If it prints an empty version and
   an empty list, the URL does not return an Atom feed.

1. Set **Debug** to `True` in the hardware settings and restart
   Domoticz.
2. Check the log right after `'onStart' called` for:
   - `"Using polling interval of ... seconds"` — confirms `onStart`
     reached the polling-interval setup.
   - Either `"Custom severity/type icon set loaded from
     meteoalarm_icons.zip."` or `"Icon zip not found at ..."` — tells
     you whether icons loaded (see *Known Limitations* below either
     way).
   - `Monitoring N region(s): ...` with the codes you configured.
   - `Devices[1] ... created.` etc. on a first start only. After a
     restart the existing devices keep their values.
3. Right after a restart **Plugin Status** shows `Starting` (grey). The
   first heartbeat fetches immediately; then confirm:
   - **Plugin Status** shows `OK` in **green**.
   - The **Last Successful Update** device shows a recent timestamp.
   - **Today**/**Tomorrow** show either a real warning (ending in the
     publish time, e.g. `[12:00]`) or the "no special awareness required"
     message in your chosen language.
4. Once you turn Debug back off, the log volume should drop back down;
   leaving Debug on generates a lot of log output on every heartbeat.

## Rolling Back

If a version doesn't work as expected:

```bash
cd /srv/domoticz/plugins/Domoticz-MeteoAlarmEU-Atom
git log --oneline -10        # find the commit/tag you want to go back to
git revert <bad-commit-hash> --no-edit   # undoes it via a new commit
git push origin master
sudo systemctl restart domoticz.service
```

Prefer `git revert` over `git reset --force` if the bad version was
already pushed/tagged publicly — revert preserves history and doesn't
require anyone else who pulled the tag to force-sync.

## Troubleshooting

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| `AttributeError: 'BasePlugin' object has no attribute 'mt'` (or similar) repeating every heartbeat | `onStart()` failed partway through on an earlier version | Check you're on 1.6.1+; this exact class of bug was fixed there |
| Plugin Status is red: `CONFIG ERROR: ...` | The feed URL or the region code list is empty or not valid (reported once in the log; nothing is polled) | Fix **RSSFeed** / **RSSCode(s)** in the hardware settings and press **Update** |
| Plugin Status is orange: `Retrying (attempt n): ...` | The last fetch failed; Today/Tomorrow still show the last good data | Read the message (timeout, HTTP error, `response is not a valid Atom feed`); retries back off 1, 2, 5, 10, 30, 60 minutes |
| Plugin Status is red `FAILING since HH:MM` and Today/Tomorrow are grey: `No data - feed unreachable` | No successful fetch for three poll intervals | Check network/DNS from the Domoticz host and the feed URL; the devices recover by themselves on the next good fetch |
| Warnings never show up although some exist | Region code does not match the feed (the log warns about a code that does not look like `LU001` or does not fit the country) | Compare the code with the `geocode=EMMA_ID:` values in the feed; a code that matches nothing looks the same as "no warning" |
| Icons don't appear | Icon-loading path is unverified against live Domoticz (see `SECURITY.md`) | Confirm `meteoalarm_icons.zip` is next to `plugin.py` and has `icons.txt` at its top level (`unzip -l meteoalarm_icons.zip \| head`); check the Debug log for the icon line and for `Could not load custom icons`; the plugin works fine without icons either way |
| Additional regions not showing up as devices | Only the first code of **RSSCode(s)** keeps Units 1/2; the others need to be in the same comma-separated list (the `Address` field is gone since 1.7.1) | Re-open the hardware settings and check the list; restart Domoticz after any hardware-setting change |
| Hardware settings come up empty after adding the hardware | The plugin manifest is not valid XML (the bare `&` bug of 1.7.0, fixed in 1.7.1) | `python3 -m unittest testManifest` in the plugin folder shows the problem; update to 1.7.1 or later |
| `Python Plugin Store: Git Fetch Error: git@github.com: Permission denied (publickey)` | A plugin in the store was cloned with an SSH URL and Domoticz has no key | Not specific to this plugin; re-clone with the HTTPS URL (see *Fresh Install*) |
| Detail text always in English despite choosing another language | `detail_dom_lang` relies on Domoticz's own language setting; an explicit language choice (e.g. "Details auf Deutsch") should always work regardless | Check **Setup → Settings → Localization → Language** if using `detail_dom_lang`, or switch Mode5 to an explicit language instead |
