# Accessibility

Weather warnings are safety information, so everyone who relies on them should be
able to read them, whatever they use to look at their Domoticz and whatever
they need to take part in this project. This page says what the project
does about that, what it has not checked, and how to tell us about a barrier.

It is written for someone who has just run into a problem, in plain words
and without standards codes.

## What this project is, and what it is not

This plugin has **no screen of its own**. It puts text and a level
into Domoticz devices. How those devices look and how you move around them
(keyboard, screen reader, magnification, colours) is decided by Domoticz and
by the web page or app you use. A barrier in the Domoticz page itself should be
reported to [Domoticz](https://www.domoticz.com/), not here.

What this project does control:

- the **text** that the Today and Tomorrow devices show,
- the **text and level** of the Plugin Status device,
- the device **names**, the log messages and the optional icons,
- the **documents** in this repository, and the issue and pull request forms.

## What we do

- **Status is written in words, not only in colour.** Plugin Status always
  carries its state as text: `Starting`, `OK`, `Retrying (attempt n)`,
  `FAILING since HH:MM` or `CONFIG ERROR`. The colour is a second signal.
  The automated tests check these texts.
- **A warning is written out.** Today and Tomorrow show the type of the warning
  in words (for example `Wind`), its level, and when the message was published.
  Unless the detail setting is `NO_DETAIL`, they also show the area and the
  time range in 24-hour time. The optional icons repeat the type, they do not
  replace it, and the default setting uses no icons.
- **The warning text can be shown in seven languages**: English, German,
  Swedish, French, Spanish, Finnish and Luxembourgish.
- **No sound, no flashing, no animation.** The plugin only updates device values.
- **Documents are structured text.** Headings go in order, tables have header
  rows, links say where they lead, and images have alternative text.
  `testCommunity.py` checks the heading order, the link texts and the image
  descriptions of every document in the repository on each test run.
- **Nobody has to say why.** You do not need to explain a disability or share
  anything personal to report a barrier or ask for a change.

## Known limitations

These are things we know do not work well. Each is a real property of the
current code, not a guess.

- **The level is a digit.** A warning reads like `Wind (3)`. The number means
  1 = green (no special awareness), 2 = yellow, 3 = orange, 4 = red, but the
  text does not say so in words. In Domoticz the level also sets the colour
  of the device. A person who cannot see the colour has to know the scale.
  Workaround: the scale is spelled out here and in the
  [README](README.md#warning-levels). Spelling the level out in the device
  text is on the [roadmap](ROADMAP.md).
- **Long warning text is cut.** The text of a day is limited to 200 characters
  and ends in `...` when it is longer. The full text is only on meteoalarm.org.
- **Plugin Status is in English only.** The warning types follow the language
  you choose, the status messages do not.
- **A grey, outdated device can keep its last warning icon.** The text then says
  `No data - feed unreachable since HH:MM`, but an icon alone could be read as a
  current warning. Plugin Status is red at the same time.
- **Some wording is not plain.** The German text for "no special awareness
  required" is informal slang, and two Luxembourgish type names (Coastal Event,
  Avalanches) are constructed words and not yet checked by a native speaker.
- **The README screenshot is an old one from the upstream project.** Its alternative
  text describes it, but the wording in the picture is not the current one
  (it still has the publish time in the device name).
- **Times are in the time zone of the Domoticz computer**, as `HH:MM`, and dates
  as day.month. (for example `5.3.`). They are not adapted to a language or a
  region.

## What has not been checked

- The plugin has **not been tested with a screen reader**, a screen
  magnifier, speech input or other assistive technology, on any Domoticz
  page or app. We make no claim that it meets a particular accessibility
  standard.
- The documents are checked by automated rules (see above) and by reading,
  not by an expert audit.
- Which Domoticz clients work well with the device texts is unknown to us.
  If you know, please tell us.

## Reporting a barrier

Use the **Accessibility barrier** form under *Issues -> New issue*. It is short,
and almost everything in it is optional. Useful to know, but never required:

- what you were trying to do and what got in the way,
- where it happened (a document, a device text, the settings form),
- how you use Domoticz or GitHub (browser or app, assistive technology).

If the form is itself hard to use, open a plain issue and write what you can.
It will be handled in the same way.

If you would rather not post in public, use the private contact route in the
[Code of Conduct](CODE_OF_CONDUCT.md).

### How we respond

This is a hobby project with one maintainer, so everything here is best
effort, with no fixed deadlines. What we will do:

- Treat the report as useful expertise.
- Say what we can and cannot change, and why. Some things, such as the Domoticz
  page itself or the MeteoAlarm feed, are outside this project.
- Offer a workaround where one exists.
- Say so in the issue when the status changes, and ask you to confirm that a
  change helps before closing it, if you are willing.

### Severity

The maintainer sets the level when going through reports. You never need to.

| Level | Meaning |
| --- | --- |
| Critical | You cannot do a core task, for example you cannot find out that a warning exists |
| Serious | Very difficult, but there is a workaround |
| Moderate | Annoying or inconsistent |
| Minor | A small effect |

Anything that makes a **warning itself** harder to read counts as at least
serious, because the warning is the whole point of the plugin.

## For contributors

- Keep the status in words. Do not make colour, position or an icon the only
  carrier of a meaning, in a device text or in a document.
- Write plain sentences. Spell out an abbreviation the first time.
- In Markdown: use real headings in order, real lists and tables with header
  rows, descriptive link text (not "here"), and alternative text for every
  image. For a picture that contains information, say that information in the
  text next to it.
- Do not add flashing or moving content.
- If you change what a device shows, say in the pull request how a person
  without colour vision, and a person using a screen reader, will read it.

## Ownership

The maintainer, [janreimen](https://github.com/janreimen), looks after this page and keeps it
in step with the code. When a limitation is fixed, it is removed from the list
above in the same change.

## Feedback

Accessibility is ongoing work, not a finished state. If something on this page
is unclear or untrue, please open an issue or a pull request.
