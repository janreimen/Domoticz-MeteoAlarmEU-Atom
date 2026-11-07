## What this changes and why

<!-- One or two sentences. Say what a user of the plugin will notice, not only which code moved. Link the issue if there is one. -->

## How it was checked

<!-- The new or changed tests, and anything you tried on a real Domoticz. Say plainly what you could not check. -->

## Checklist

- [ ] The change is about one thing.
- [ ] There is a test, and it **fails without my change** (revert the fix and run it once).
- [ ] The whole suite passes: `python3 -m unittest discover -p 'test*.py'`, and `ruff check .` is clean.
- [ ] `CHANGELOG.md` has an entry. If the devices show something different afterwards, it is marked as a behaviour change.
- [ ] If the version changed, `plugin.py` (manifest), `PLUGIN_VERSION` in `meteo.py`, the top of `CHANGELOG.md` and the README badge agree.
- [ ] A plugin problem is still shown on Plugin Status and never as a weather level.
- [ ] Device names and unit numbers are unchanged, or the change is explained above.
- [ ] Anything I could not verify against a live Domoticz or the live feed is marked as unverified.
- [ ] No private data in the code, the tests or the logs I pasted.

### Only if you changed documentation or texts the devices show

- [ ] Headings go in order, links say where they lead, images have alternative text.
- [ ] Meaning is not carried by colour alone, and the wording is plain.

By sending this pull request you agree that it is released under the project's [GPL-3.0 licence](https://github.com/janreimen/Domoticz-MeteoAlarmEU-Atom/blob/master/LICENSE) and that you follow the [Code of Conduct](https://github.com/janreimen/Domoticz-MeteoAlarmEU-Atom/blob/master/CODE_OF_CONDUCT.md). The [contributing guide](https://github.com/janreimen/Domoticz-MeteoAlarmEU-Atom/blob/master/CONTRIBUTING.md) explains the rules behind the checklist.
