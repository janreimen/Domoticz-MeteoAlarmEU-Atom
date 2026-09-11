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
   **MeteoAlarmEU Atom**.

7. **Configure it** — see `README.md` → *Settings* for what each field
   means (feed URL, region code(s), language, icons).

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

4. **Device IDs are stable across upgrades** — the primary region always
   keeps Units 1 (Today) and 2 (Tomorrow), so existing dashboards/
   automations tied to those devices keep working after an upgrade.
   Additional-region devices (if you use that 1.7.0+ feature) and the
   Plugin Status/Last Successful Update devices (Units 3/4) are created
   automatically on first start if they don't already exist.

5. **If you were on a pre-1.6.3 version:** the feed format itself
   changed upstream (meteoalarm.org sunset legacy RSS), and the parser
   was rewritten to match. There's nothing you need to do differently,
   but expect device text formatting to look different after upgrading,
   since the whole parsing approach changed with it.

## Verifying It's Running Correctly

1. Set **Debug** to `True` in the hardware settings and restart
   Domoticz.
2. Check the log right after `'onStart' called` for:
   - `"Using polling interval of ... seconds"` — confirms `onStart`
     reached the polling-interval setup.
   - Either `"Custom severity/type icon set loaded from
     meteoalarm_icons.zip."` or `"Icon zip not found at ..."` — tells
     you whether icons loaded (see *Known Limitations* below either
     way).
   - `Devices[1] created.` / `Devices[2] created.` (and `[3]`/`[4]` for
     Plugin Status / Last Successful Update).
3. Wait for the first heartbeat poll (or force a Domoticz restart to
   trigger `onStart` again) and confirm:
   - The **Plugin Status** device shows `OK`.
   - The **Last Successful Update** device shows a recent timestamp.
   - **Today**/**Tomorrow** show either a real warning or the
     "no special awareness required" message in your chosen language —
     not `ERROR!!!`.
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
| Devices show `ERROR!!!` constantly | Feed unreachable, wrong URL, or wrong region code | Check **RSSFeed** is a `...legacy-atom-<country>` URL, not `legacy-rss-*`; verify the region code against meteoalarm.org's geocodes JSON |
| Icons don't appear | Icon-loading path is unverified against live Domoticz (see `SECURITY.md`) | Confirm `meteoalarm_icons.zip` is present next to `plugin.py`; check Debug log for the icon-loading line; the plugin works fine without icons either way |
| Additional regions (`Address` field) not showing up as devices | Field may not have saved correctly, or Domoticz restart needed after changing it | Re-open hardware settings to confirm the value saved; restart Domoticz after any hardware-setting change |
| Detail text always in English despite choosing another language | `detail_dom_lang` relies on Domoticz's own language setting; an explicit language choice (e.g. "Details auf Deutsch") should always work regardless | Check **Setup → Settings → Localization → Language** if using `detail_dom_lang`, or switch Mode5 to an explicit language instead |
