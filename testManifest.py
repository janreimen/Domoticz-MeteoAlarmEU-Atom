"""
testManifest.py - lint tests for what Domoticz reads from this repo
WITHOUT running any plugin code: the XML manifest at the top of plugin.py
and the bundled icon zip.

Both have already caused real "plugin looks broken" incidents:

* 1.7.0/1.7.1 - a bare '&' in `externallink` made the manifest invalid XML,
  so the Add Hardware form came up empty and hardware was created with
  empty Mode1-6 columns. Domoticz extracts the manifest with a plain line
  scan from '<plugin' to '</plugin>' (PluginManager.cpp, BuildManifest) and
  parses that text as XML - extract_manifest() below does the same.
* the icon zip must have icons.txt at its ROOT; a zip packed on macOS (a
  subfolder plus a __MACOSX directory) does not.

Run with:
    python3 -m unittest testManifest
"""
import os
import re
import unittest
import xml.etree.ElementTree as ET
import zipfile

import meteo

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_PY = os.path.join(HERE, "plugin.py")
CHANGELOG = os.path.join(HERE, "CHANGELOG.md")
ICON_ZIP = os.path.join(HERE, "meteoalarm_icons.zip")

VALID_PARAM_FIELDS = {"Address", "Port", "SerialPort", "Username", "Password",
                      "Mode1", "Mode2", "Mode3", "Mode4", "Mode5", "Mode6"}


def extract_manifest(path=PLUGIN_PY):
    """the text Domoticz would hand to its XML parser: every line from the
    one containing '<plugin' up to the one containing '</plugin>'."""
    lines = []
    inside = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not inside and "<plugin" in line:
                inside = True
            if inside:
                lines.append(line)
                if "</plugin>" in line:
                    break
    return "".join(lines)


class TestManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = extract_manifest()
        cls.root = ET.fromstring(cls.text)  # raises on a bare '&', unclosed tag, ...

    def test_manifest_is_well_formed_xml(self):
        self.assertEqual(self.root.tag, "plugin")

    def test_plugin_tag_appears_on_exactly_one_line_before_the_manifest(self):
        # the line scan starts at the FIRST line containing '<plugin' - a
        # mention inside the version-history text would start it too early
        with open(PLUGIN_PY, encoding="utf-8") as f:
            hits = [n for n, line in enumerate(f, 1) if "<plugin" in line]
        self.assertEqual(len(hits), 1, "'<plugin' occurs on lines {}".format(hits))

    def test_required_attributes_are_present(self):
        for attribute in ("key", "name", "author", "version"):
            self.assertTrue(self.root.get(attribute), "missing attribute '{}'".format(attribute))

    def test_key_is_a_clean_identifier(self):
        self.assertRegex(self.root.get("key"), r"^[A-Za-z0-9_-]+$",
                         "the key is stored in the Hardware table; keep it free of spaces")

    def test_externallink_is_a_plain_web_url(self):
        link = self.root.get("externallink")
        self.assertRegex(link, r"^https?://")
        self.assertFalse(link.endswith(".git"), "externallink is opened in a browser, not cloned")

    def test_manifest_version_matches_code_and_changelog(self):
        self.assertEqual(self.root.get("version"), meteo.PLUGIN_VERSION)
        with open(CHANGELOG, encoding="utf-8") as f:
            top = re.search(r"^## \[([^\]]+)\]", f.read(), re.MULTILINE).group(1)
        self.assertEqual(top, meteo.PLUGIN_VERSION, "top CHANGELOG entry is not the current version")

    def test_every_param_uses_a_valid_unique_field(self):
        fields = [p.get("field") for p in self.root.iter("param")]
        for field in fields:
            self.assertIn(field, VALID_PARAM_FIELDS)
        self.assertEqual(len(fields), len(set(fields)), "duplicate param fields: {}".format(fields))

    def test_required_text_params_have_a_default(self):
        for p in self.root.iter("param"):
            if p.find("options") is None and p.get("required") == "true":
                self.assertTrue(p.get("default"), "{} is required but has no default".format(p.get("field")))

    def test_every_dropdown_marks_exactly_one_default_with_selected(self):
        # this project marks defaults with selected="selected" (maintainer
        # decision, 1.7.2) - not with default="..." on an <option>
        for p in self.root.iter("param"):
            options = p.find("options")
            if options is None:
                continue
            chosen = [o.get("value") for o in options if o.get("selected") == "selected"]
            self.assertEqual(len(chosen), 1, "{}: selected options = {}".format(p.get("field"), chosen))
            self.assertFalse([o for o in options if o.get("default") is not None],
                             "{}: use selected=\"selected\", not default=".format(p.get("field")))

    def test_dropdown_values_are_unique(self):
        for p in self.root.iter("param"):
            options = p.find("options")
            if options is not None:
                values = [o.get("value") for o in options]
                self.assertEqual(len(values), len(set(values)), p.get("field"))

    def test_debug_defaults_to_off(self):
        debug = [p for p in self.root.iter("param") if p.get("field") == "Mode4"][0]
        selected = [o.get("value") for o in debug.find("options") if o.get("selected") == "selected"]
        self.assertEqual(selected, ["Normal"], "a fresh hardware must not start with debug logging on")

    def test_every_detail_language_option_has_a_translation_column(self):
        details = [p for p in self.root.iter("param") if p.get("field") == "Mode5"][0]
        languages = [o.get("value") for o in details.find("options")
                     if o.get("value") not in ("no_detail", "detail_dom_lang")]
        for language in languages:
            self.assertIn(language.lower(), meteo.Meteo.LANG_NAME_TO_INDEX, language)

    def test_default_poll_interval_matches_the_code(self):
        import plugin
        poll = [p for p in self.root.iter("param") if p.get("field") == "Mode3"][0]
        self.assertEqual(int(poll.get("default")), plugin.DEFAULT_POLL_MINUTES)

    def test_default_region_codes_pass_the_plugins_own_validation(self):
        feed = [p for p in self.root.iter("param") if p.get("field") == "Mode1"][0].get("default")
        codes = [p for p in self.root.iter("param") if p.get("field") == "Mode2"][0].get("default")
        errors, warnings, _ = meteo.validateConfig(feed, codes)
        self.assertEqual((errors, warnings), ([], []))


class TestIconZip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zf = zipfile.ZipFile(ICON_ZIP)
        cls.names = cls.zf.namelist()

    def test_zip_is_not_corrupt(self):
        self.assertIsNone(self.zf.testzip())

    def test_icons_txt_is_at_the_zip_root(self):
        self.assertIn("icons.txt", self.names)

    def test_no_subfolders_and_no_macos_leftovers(self):
        bad = [n for n in self.names if "/" in n or n.startswith("._") or n.endswith(".DS_Store")]
        self.assertEqual(bad, [], "pack the zip flat (e.g. `zip -j`) and without __MACOSX/")

    def _prefixes(self):
        lines = self.zf.read("icons.txt").decode("utf-8").strip().splitlines()
        return [line.split(";")[0] for line in lines]

    def test_icons_txt_lines_have_three_fields(self):
        for line in self.zf.read("icons.txt").decode("utf-8").strip().splitlines():
            self.assertEqual(len(line.split(";")), 3, line)

    def test_every_icon_has_all_five_image_files(self):
        for p in self._prefixes():
            for suffix in (".png", "_On.png", "_Off.png", "48_On.png", "48_Off.png"):
                self.assertIn(p + suffix, self.names)

    def test_no_orphan_image_files(self):
        expected = set()
        for p in self._prefixes():
            expected.update(p + s for s in (".png", "_On.png", "_Off.png", "48_On.png", "48_Off.png"))
        pngs = {n for n in self.names if n.endswith(".png")}
        self.assertEqual(sorted(pngs - expected), [])

    def test_icon_set_covers_every_warning_type_and_level_the_code_can_ask_for(self):
        prefixes = set(self._prefixes())
        for typeName in meteo.Meteo.ICON_NAME_BY_AWT.values():
            for level in (1, 2, 3, 4):
                self.assertIn("{}{}L{}".format(meteo.Meteo.ICON_FILE_PREFIX, typeName, level), prefixes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
