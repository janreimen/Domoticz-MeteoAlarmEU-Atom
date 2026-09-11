# Security Policy

## Supported Versions

Only the latest tagged release is supported. This is a small,
single-maintainer hobbyist plugin, not a commercially maintained
project — there is no backporting of fixes to older versions.

| Version | Supported |
| ------- | --------- |
| 1.7.x   | ✅ |
| < 1.7   | ❌ |

## What's in scope

This plugin's realistic attack surface is narrow, but worth naming
explicitly:

- **Outbound HTTP requests** to a configured `feeds.meteoalarm.org` URL
  (or whatever URL is entered in the *RSSFeed* hardware setting — the
  plugin does not restrict this to meteoalarm.org, so a malicious or
  compromised feed URL is a real, if self-inflicted, risk).
- **XML/Atom feed parsing** via `feedparser`, of content fetched from
  that URL. `feedparser` handles untrusted XML safely by design, but a
  vulnerability in that dependency would apply here too.
- **The bundled icon zip** (`meteoalarm_icons.zip`), loaded via
  Domoticz's own `Domoticz.Image()` mechanism at `onStart()`.

## What's explicitly NOT in scope

- This plugin does not handle authentication, secrets, or credentials of
  any kind.
- It does not accept inbound network connections — Domoticz's plugin
  framework and `onCommand` are Domoticz's own responsibility, not this
  plugin's.
- Domoticz itself, `feedparser`, and other third-party dependencies —
  report those upstream, not here.

## Reporting a Vulnerability

If you find a security issue (e.g. the plugin fetching/rendering
unsanitized feed content in a way that could be abused, or a dependency
issue specific to how this plugin uses it):

1. **Do not open a public GitHub issue for it.**
2. Open a private report via GitHub's "Report a vulnerability" flow
   under this repository's **Security** tab (uses GitHub Security
   Advisories), or contact the maintainer directly if that's not
   available.
3. Include: the plugin version (from the `version=` attribute in
   `plugin.py`'s XML header), Domoticz version, and steps to reproduce.

Given the scope of this plugin (a weather-alert display integration, no
credential handling, no inbound connections), response times are
best-effort — this is a hobbyist project maintained outside working
hours.

## Known Limitations (not vulnerabilities, but worth knowing)

- `getDayIconKey()`'s icon-loading path (`meteoalarm_icons.zip` via
  `Domoticz.Image()`) has not been verified against a live Domoticz
  instance — see `README.md` → *Bugs and ToDos*. A failure there is
  handled defensively (falls back to the default icon) and is not a
  security issue, just an unverified feature.
