# Contributing

Thanks for helping with MeteoAlarmEU-Atom. This is a small plugin with one
maintainer, so the aim of this page is to make a good bug report or pull
request quick to write and quick to review.

- Contributions are released under the project's licence, the
  [GPL-3.0](LICENSE), like the upstream projects this was forked from.
- Everyone taking part is expected to follow the
  [Code of Conduct](CODE_OF_CONDUCT.md).
- Barriers in the documentation, the device texts or the way you can take part
  are welcome as reports: see [`ACCESSIBILITY.md`](ACCESSIBILITY.md).
- A security problem is **not** a public issue: see
  [`SECURITY.md`](SECURITY.md).

Replies are best effort. This is a hobby project maintained outside working
hours, so a few days of silence does not mean the report was ignored.

## Reporting a bug

Use the **Bug report** form (*Issues -> New issue*). It asks for the things
that decide most bugs here:

1. The plugin version, Domoticz version and Python version.
2. What **Plugin Status** shows (colour and text). It tells apart a feed
   problem, a configuration problem and a parsing problem.
3. The Domoticz log with **Debug** set to `True`, from the start of the plugin
   (`'onStart' called`) to the problem. Remove anything private first. The
   plugin handles no passwords or tokens, but a log can still contain your
   host names.
4. For a *wrong or missing warning*: the region code you configured and, if you
   can, the matching `<entry>` from the live feed. `DEPLOY.md` -> *Verifying
   it's running correctly* has a one-line check you can run.

A region code that matches nothing looks exactly like "no warning today",
because the feed only lists active warnings. Please compare your code with the
`geocode=EMMA_ID:` values in the feed before reporting a missing warning.

## Suggesting a feature

Use the **Feature request** form. Say what you want to *do* (for example "close
the blinds on a wind warning of level 3 or higher") and not only what you want
changed. Look at [`ROADMAP.md`](ROADMAP.md) first; the idea may already be
there with a note on why it is not done yet.

## Setting up

```bash
git clone https://github.com/janreimen/Domoticz-MeteoAlarmEU-Atom.git
cd Domoticz-MeteoAlarmEU-Atom
pip install -r requirements.txt -r requirements-dev.txt
python3 -m unittest discover -p 'test*.py' -v
ruff check .
```

You do not need Domoticz to develop or test: `fakeDomoticz.py` stands in for
the framework. Python 3.11 to 3.13 is what CI runs.

| File | What it is |
| --- | --- |
| `plugin.py` | The Domoticz side: the manifest, `onStart`/`onHeartbeat`, devices, Plugin Status, retry and stale handling |
| `meteo.py` | No Domoticz code beyond logging: fetching, parsing, region matching, day splitting, translations. Keep it that way, it is what makes the tests possible |
| `fakeDomoticz.py` | A small stand-in for the Domoticz plugin framework, used by the tests |
| `testMeteo.py` | Parser and text tests on a frozen clock |
| `testPlugin.py` | End-to-end tests of `onStart`/`onHeartbeat` with a scripted feed |
| `testManifest.py` | Lints the plugin manifest and the icon zip the way Domoticz reads them |
| `testCommunity.py` | Checks the community files, the issue forms and the Markdown documents |
| `meteoalarm_icons.zip` | The bundled icon set, `icons.txt` at the zip root |

## Making a change

1. Fork, then branch from `master`.
2. **Write the test first**, and check that it fails without your change. A
   test that passes either way proves nothing. The easiest way to check is to
   revert your fix and run the test again.
3. Make the change. Keep the pull request about one thing.
4. Add an entry to [`CHANGELOG.md`](CHANGELOG.md) under the version you are
   working on, and describe what a *user* will notice, not only the code.
5. Run the whole suite and `ruff check .`.
6. Open the pull request. The template has a short checklist.

### Rules that come from earlier mistakes

- **A plugin problem must never look like a weather alert.** Today/Tomorrow
  levels describe the weather only. Feed, network and configuration problems go
  to **Plugin Status**.
- **Never rename a device on update.** Scripts refer to devices by name. A name
  is set when the device is created.
- **Unit numbers are stable.** The first region keeps Units 1/2, Plugin Status is
  3 and Last Successful Update is 4. Do not renumber.
- **The manifest at the top of `plugin.py` is XML.** Domoticz reads it with a
  line scan from `<plugin` to `</plugin>`. A bare `&` makes the settings form
  come up empty. `testManifest.py` catches this; write `&amp;`.
- **Mark every dropdown default** with `selected="selected"` on exactly one
  `<option>`.
- **Per-heartbeat log lines go to `Domoticz.Debug`.** `Domoticz.Log` is for
  things that changed.
- **Times from the feed are UTC.** Convert with `calendar.timegm`, never
  `time.mktime`.
- **Do not claim what you have not seen.** If a behaviour is unverified against
  a live Domoticz or the live feed, say so in the code comment, the changelog or
  the pull request.

### Changing the version number

The version appears in three places, and `testManifest.py` fails if they
disagree: the `version="..."` attribute in the manifest of `plugin.py`,
`PLUGIN_VERSION` in `meteo.py`, and the top entry of `CHANGELOG.md`. The
badge in `README.md` should follow.

### Translations

The warning type names live in `Meteo.AWT_TRANSLATION` in `meteo.py`, one list
per type in the order English, German, Swedish, French, Spanish, Finnish,
Luxembourgish. To add a language, add an entry to every list, to
`Meteo.LANG_NAME_TO_INDEX`, to the `Mode5` dropdown in the manifest and, if
Domoticz has a language code for it, to `Meteo.DOM_LANG_TO_METEO`. If you are
not sure a translation is natural, say so in the pull request; two of the
Luxembourgish ones are known to be constructed (see `README.md` -> *Bugs and
ToDos*).

### Feed samples in tests

When a parser change depends on what the feed contains, add a small, shortened
sample as test data and say where it came from and when. Do not paste a whole
feed.

## Pull request review

Expect questions about *why* before *what*. A pull request that changes what
the devices show is held to the rules above and is described in the changelog
as a behaviour change, with what to do about it.

## Releases (maintainer)

1. The whole suite is green on Python 3.11, 3.12 and 3.13 (CI).
2. The three version places agree and `CHANGELOG.md` has an entry for the
   version.
3. Tag `vX.Y.Z` and publish a GitHub Release with the changelog entry as its
   text.

## Useful reading

- [How to contribute to open source](https://opensource.guide/how-to-contribute/)
- [About pull requests](https://docs.github.com/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests)
