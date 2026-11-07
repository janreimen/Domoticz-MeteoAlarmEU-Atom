"""
testCommunity.py - checks that the files around the code stay in good shape:
the community files GitHub looks for, the issue forms, and the Markdown
documents (links, anchors, heading order, image descriptions).

Nothing here runs plugin code. These are the kind of mistakes that do not
break the plugin but break the project for the next person:

* an issue form with a typo in its YAML silently turns into a blank issue,
* a link to a renamed file or heading leads nowhere,
* a version badge that still shows the last release,
* a copied template that still contains "[INSERT CONTACT METHOD]".

Run with:
    python3 -m unittest testCommunity

The issue-form checks need PyYAML (requirements-dev.txt). Without it they are
skipped on a developer machine and FAIL when the CI environment variable is
set, so CI can never pass without having checked the forms.
"""
import glob
import os
import re
import unittest

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the environment
    yaml = None

import meteo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_URL = "https://github.com/janreimen/Domoticz-MeteoAlarmEU-Atom"
BLOB_PREFIX = REPO_URL + "/blob/master/"
SECURITY_ADVISORY_URL = REPO_URL + "/security/advisories/new"

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "ACCESSIBILITY.md",
    "CHANGELOG.md",
    "ROADMAP.md",
    "DEPLOY.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/warning_problem.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/accessibility.yml",
    "requirements-dev.txt",
]

# files that must not contain text left over from a template
PLACEHOLDER_CHECKED = [f for f in REQUIRED_FILES if f != "LICENSE"]
PLACEHOLDER_PATTERNS = [
    r"\[INSERT[^\]]*\]",
    r"<INSERT[^>]*>",
    r"\[maintainer name[^\]]*\]",
    r"\[your[- ](e-?mail|name)[^\]]*\]",
    r"conduct@ethicalsource\.dev",
    r"github\.com/github/REPO",
    r"\bFIXME\b",
    r"\bTODO\b",
]

GENERIC_LINK_TEXTS = {"here", "click here", "this link", "link", "read more", "more", "this", "page"}


def path_of(rel):
    return os.path.join(HERE, *rel.split("/"))


def read(rel):
    with open(path_of(rel), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- Markdown

def markdown_files():
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, "*.md")))
    return names + [".github/PULL_REQUEST_TEMPLATE.md"]


def prose_lines(text, mask_code=True):
    """(lineno, line) for every line outside fenced code blocks. With
    mask_code, brackets and parentheses inside `inline code` are neutralised
    so that `[x](y)` in backticks is not read as a link, while the words in it
    still count as text (a link whose text is `README.md` has a text)."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is not None:
            continue
        if mask_code:
            line = re.sub(r"`([^`]*)`", lambda m: re.sub(r"[\[\]()!]", "_", m.group(1)) or "_", line)
        yield number, line


def headings(text):
    """[(lineno, level, title)]"""
    found = []
    for number, line in prose_lines(text, mask_code=False):
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            found.append((number, len(m.group(1)), m.group(2)))
    return found


def github_slug(title):
    """the anchor GitHub makes from a heading (without the -1, -2 suffixes
    for duplicates, which anchors() adds)."""
    title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)   # links keep their text
    title = title.replace("`", "")
    title = re.sub(r"[*_~]+(\S.*?\S|\S)[*_~]+", r"\1", title)  # emphasis
    title = title.lower()
    title = re.sub(r"[^\w\- ]", "", title)
    return title.replace(" ", "-")


def anchors(text):
    seen = {}
    result = set()
    for _, _, title in headings(text):
        slug = github_slug(title)
        count = seen.get(slug, 0)
        result.add(slug if count == 0 else "{}-{}".format(slug, count))
        seen[slug] = count + 1
    return result


IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")


def images_and_links(text):
    """(images, links), each a list of (lineno, text_or_alt, target). An image
    inside a link (a badge) counts as an image, and its alt text becomes the
    text of the link."""
    images, links = [], []
    for number, line in prose_lines(text):
        for m in IMAGE.finditer(line):
            images.append((number, m.group(1), m.group(2).strip()))
        plain = IMAGE.sub(lambda m: m.group(1), line)
        for m in LINK.finditer(plain):
            links.append((number, m.group(1), m.group(2).strip().split(" ")[0]))
    return images, links


def resolve_local(rel_file, target):
    """(path_exists, anchor_exists_or_None) for a link target found in rel_file
    that points inside the repository. target may be relative, or an absolute
    https://github.com/.../blob/master/ URL."""
    anchor = None
    if "#" in target:
        target, anchor = target.split("#", 1)
    if target.startswith(BLOB_PREFIX):
        rel = target[len(BLOB_PREFIX):]
        full = path_of(rel)
    elif target == "":
        full = path_of(rel_file)
    else:
        full = os.path.normpath(os.path.join(os.path.dirname(path_of(rel_file)), target))
    if not os.path.exists(full):
        return False, None
    if anchor is None:
        return True, None
    if not full.endswith(".md"):
        return True, None
    with open(full, encoding="utf-8") as f:
        return True, anchor in anchors(f.read())


class TestRequiredFiles(unittest.TestCase):
    def test_every_required_file_exists_and_is_not_empty(self):
        for rel in REQUIRED_FILES:
            with self.subTest(file=rel):
                self.assertTrue(os.path.isfile(path_of(rel)), rel + " is missing")
                self.assertGreater(os.path.getsize(path_of(rel)), 100 if rel.endswith((".md", ".yml")) else 5,
                                   rel + " is nearly empty")

    def test_no_template_leftovers(self):
        for rel in PLACEHOLDER_CHECKED:
            text = read(rel)
            for pattern in PLACEHOLDER_PATTERNS:
                with self.subTest(file=rel, pattern=pattern):
                    self.assertIsNone(re.search(pattern, text), "{} still contains {}".format(rel, pattern))

    def test_license_is_the_full_gpl_text(self):
        text = read("LICENSE")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", text)
        self.assertIn("Version 3", text)
        self.assertGreater(len(text), 30000)

    def test_code_of_conduct_keeps_its_attribution_and_has_a_contact_route(self):
        text = read("CODE_OF_CONDUCT.md")
        self.assertIn("Contributor Covenant", text)
        self.assertIn("CC BY-SA 4.0", text)
        self.assertIn("https://github.com/janreimen", text, "no way to report is named")

    def test_accessibility_statement_has_the_parts_a_reader_needs(self):
        titles = [t for _, _, t in headings(read("ACCESSIBILITY.md"))]
        for wanted in ("Known limitations", "Reporting a barrier", "What has not been checked"):
            self.assertIn(wanted, titles)

    def test_accessibility_statement_does_not_claim_conformance(self):
        # Nobody has evaluated this project against a standard, so the statement must not
        # say it conforms to or complies with one, in either word order. Naming a standard
        # (WCAG) is not claimed either: the text says no standard is claimed.
        text = read("ACCESSIBILITY.md").replace("\n", " ")
        self.assertNotRegex(text, r"(?i)\b(conform\w*|compl(y|ies|iant|iance))\b")
        self.assertNotRegex(text, r"(?i)\bWCAG\b")
        self.assertIn("not been tested with a screen reader", text)
        self.assertIn("no claim", text)


class TestVersionAgreement(unittest.TestCase):
    def test_readme_badge_shows_the_current_version(self):
        m = re.search(r"badge/version-([0-9][0-9.]*)-", read("README.md"))
        self.assertIsNotNone(m, "version badge not found in README.md")
        self.assertEqual(m.group(1), meteo.PLUGIN_VERSION)

    def test_security_policy_lists_the_current_release_line(self):
        major_minor = ".".join(meteo.PLUGIN_VERSION.split(".")[:2])
        row = re.search(r"^\|\s*{}\.x\s*\|\s*(\S+)".format(re.escape(major_minor)), read("SECURITY.md"), re.M)
        self.assertIsNotNone(row, "SECURITY.md has no row for {}.x".format(major_minor))
        self.assertNotEqual(row.group(1), "❌")

    def test_security_report_link_is_the_same_everywhere(self):
        # exact match: a plain substring test would also accept ".../new2" or ".../new/x"
        exact = re.compile(re.escape(SECURITY_ADVISORY_URL) + r"(?![\w/.#?-])")
        self.assertRegex(read("SECURITY.md"), exact)
        self.assertRegex(read(".github/ISSUE_TEMPLATE/config.yml"), exact)


class TestContributingGuide(unittest.TestCase):
    def test_every_file_in_the_layout_table_exists(self):
        names = re.findall(r"^\|\s*`([^`]+)`\s*\|", read("CONTRIBUTING.md"), re.M)
        self.assertGreaterEqual(len(names), 6, "the file table was not found")
        for name in names:
            with self.subTest(file=name):
                self.assertTrue(os.path.exists(path_of(name)), name + " is listed but does not exist")

    def test_every_test_file_is_in_the_layout_table(self):
        table = read("CONTRIBUTING.md")
        for path in sorted(glob.glob(os.path.join(HERE, "test*.py"))):
            name = os.path.basename(path)
            with self.subTest(file=name):
                self.assertIn("`{}`".format(name), table)


class TestMarkdownDocuments(unittest.TestCase):
    def test_there_is_one_h1_and_heading_levels_do_not_skip(self):
        for rel in markdown_files():
            levels = headings(read(rel))
            with self.subTest(file=rel):
                # a pull request description sits under the pull request's own title,
                # so its template starts at level 2
                expected_h1 = 0 if rel == ".github/PULL_REQUEST_TEMPLATE.md" else 1
                self.assertEqual(sum(1 for _, lv, _ in levels if lv == 1), expected_h1,
                                 "wrong number of # headings")
                previous = 0
                for number, level, title in levels:
                    if previous:
                        self.assertLessEqual(level, previous + 1,
                                             "{}:{} '{}' skips a heading level".format(rel, number, title))
                    previous = level

    def test_images_have_a_description(self):
        for rel in markdown_files():
            images, _ = images_and_links(read(rel))
            for number, alt, target in images:
                with self.subTest(file=rel, line=number):
                    self.assertTrue(alt.strip(), "{}:{} image {} has no alternative text".format(rel, number, target))
                    self.assertNotRegex(alt, r"(?i)\.(png|jpe?g|gif|svg)$",
                                        "{}:{} alternative text is a file name".format(rel, number))

    def test_links_have_a_target_and_a_meaningful_text(self):
        for rel in markdown_files():
            _, links = images_and_links(read(rel))
            for number, text, target in links:
                with self.subTest(file=rel, line=number, link=text):
                    self.assertTrue(target, "{}:{} link '{}' has no target".format(rel, number, text))
                    self.assertTrue(text.strip(), "{}:{} link to {} has no text".format(rel, number, target))
                    self.assertNotIn(text.strip().lower(), GENERIC_LINK_TEXTS,
                                     "{}:{} link text '{}' does not say where it leads".format(rel, number, text))

    def test_links_inside_the_repository_resolve(self):
        for rel in markdown_files():
            images, links = images_and_links(read(rel))
            targets = links + images
            for number, text, target in targets:
                if re.match(r"^[a-z][a-z0-9+.-]*:", target) and not target.startswith(BLOB_PREFIX):
                    continue  # another site, or mailto:
                with self.subTest(file=rel, line=number, target=target):
                    path_ok, anchor_ok = resolve_local(rel, target)
                    self.assertTrue(path_ok, "{}:{} -> {} does not exist".format(rel, number, target))
                    if anchor_ok is not None:
                        self.assertTrue(anchor_ok, "{}:{} -> {} has no such heading".format(rel, number, target))

    def test_pull_request_template_uses_absolute_links(self):
        # a relative link in a pull request description would be resolved
        # against the pull request page, not against the repository
        _, links = images_and_links(read(".github/PULL_REQUEST_TEMPLATE.md"))
        self.assertTrue(links)
        for number, text, target in links:
            with self.subTest(line=number, link=text):
                self.assertTrue(target.startswith("https://"), "relative link in the PR template: " + target)


@unittest.skipIf(yaml is None and not os.environ.get("CI"), "PyYAML not installed (pip install -r requirements-dev.txt)")
class TestIssueForms(unittest.TestCase):
    ALLOWED_TYPES = {"markdown", "textarea", "input", "dropdown", "checkboxes"}
    FORMS = sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, ".github", "ISSUE_TEMPLATE", "*.yml"))
                   if os.path.basename(p) != "config.yml")

    @classmethod
    def setUpClass(cls):
        if yaml is None:
            raise AssertionError("PyYAML is missing in CI: the issue forms would go unchecked")

    def load(self, name):
        with open(path_of(".github/ISSUE_TEMPLATE/" + name), encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_the_expected_forms_are_there(self):
        self.assertEqual(set(self.FORMS), {"bug_report.yml", "warning_problem.yml",
                                           "feature_request.yml", "accessibility.yml"})

    def test_each_form_has_the_structure_github_requires(self):
        for name in self.FORMS:
            data = self.load(name)
            with self.subTest(form=name):
                for key in ("name", "description"):
                    self.assertIsInstance(data.get(key), str, key)
                    self.assertTrue(data[key].strip(), key)
                self.assertIsInstance(data.get("body"), list)
                self.assertTrue(data["body"])
                labels = data.get("labels", [])
                self.assertIsInstance(labels, list)
                self.assertTrue(all(isinstance(x, str) for x in labels))
                ids = []
                required = 0
                for index, element in enumerate(data["body"]):
                    where = "{} element {}".format(name, index)
                    self.assertIn(element.get("type"), self.ALLOWED_TYPES, where)
                    attributes = element.get("attributes")
                    self.assertIsInstance(attributes, dict, where)
                    if element["type"] == "markdown":
                        self.assertTrue(str(attributes.get("value", "")).strip(), where)
                        continue
                    self.assertTrue(str(attributes.get("label", "")).strip(), where + " has no label")
                    identifier = element.get("id")
                    self.assertRegex(str(identifier), r"^[A-Za-z0-9_-]+$", where + " needs an id")
                    ids.append(identifier)
                    if element["type"] == "dropdown":
                        options = attributes.get("options")
                        self.assertIsInstance(options, list, where)
                        self.assertGreaterEqual(len(options), 2, where)
                        self.assertEqual(len(options), len(set(options)), where + " has duplicate options")
                    if element["type"] == "checkboxes":
                        options = attributes.get("options")
                        self.assertTrue(options, where)
                        for option in options:
                            self.assertTrue(str(option.get("label", "")).strip(), where)
                    if (element.get("validations") or {}).get("required") is True:
                        required += 1
                self.assertEqual(len(ids), len(set(ids)), name + " has duplicate ids")
                self.assertGreaterEqual(required, 1, name + " has no required field at all")

    def test_links_in_the_forms_are_absolute_and_resolve(self):
        for name in self.FORMS:
            data = self.load(name)
            text = "\n".join(str(e["attributes"].get("value", "")) for e in data["body"] if e["type"] == "markdown")
            _, links = images_and_links(text)
            for number, label, target in links:
                with self.subTest(form=name, link=label):
                    self.assertTrue(target.startswith("https://"), "relative link in a form: " + target)
                    if target.startswith(BLOB_PREFIX):
                        path_ok, anchor_ok = resolve_local("README.md", target)
                        self.assertTrue(path_ok, target + " does not exist")
                        if anchor_ok is not None:
                            self.assertTrue(anchor_ok, target + " has no such heading")

    def test_the_issue_chooser_config(self):
        data = self.load("config.yml")
        self.assertIsInstance(data.get("blank_issues_enabled"), bool)
        # on purpose: someone for whom a form is a barrier must still be able to write a plain issue
        self.assertTrue(data["blank_issues_enabled"])
        links = data.get("contact_links")
        self.assertIsInstance(links, list)
        self.assertTrue(links)
        for entry in links:
            with self.subTest(link=entry.get("name")):
                for key in ("name", "url", "about"):
                    self.assertTrue(str(entry.get(key, "")).strip(), key)
                self.assertTrue(entry["url"].startswith("https://"))
                if entry["url"].startswith(BLOB_PREFIX):
                    path_ok, anchor_ok = resolve_local("README.md", entry["url"])
                    self.assertTrue(path_ok, entry["url"])
                    if anchor_ok is not None:
                        self.assertTrue(anchor_ok, entry["url"])


class TestHelpers(unittest.TestCase):
    """the checks above are only as good as these helpers"""

    def test_github_slug(self):
        self.assertEqual(github_slug("Verifying It's Running Correctly"), "verifying-its-running-correctly")
        self.assertEqual(github_slug("Upgrading from 1.7.0 / 1.7.1 to 1.7.2"), "upgrading-from-170--171-to-172")
        self.assertEqual(github_slug("Plugin Status colours"), "plugin-status-colours")
        self.assertEqual(github_slug("The `Address` field"), "the-address-field")

    def test_duplicate_headings_get_numbered_anchors(self):
        self.assertEqual(anchors("# T\n## Same\n## Same\n"), {"t", "same", "same-1"})

    def test_code_blocks_and_inline_code_are_not_read_as_markdown(self):
        text = "# T\n```\n# not a heading\n[a](b)\n```\nSee `[x](y)` and [real](README.md).\n"
        self.assertEqual([t for _, _, t in headings(text)], ["T"])
        _, links = images_and_links(text)
        self.assertEqual([(t, tg) for _, t, tg in links], [("real", "README.md")])

    def test_badge_link_is_an_image_and_a_link_with_the_alt_text(self):
        images, links = images_and_links("[![Build status](https://x/y.svg)](https://x/z)\n")
        self.assertEqual([(a, t) for _, a, t in images], [("Build status", "https://x/y.svg")])
        self.assertEqual([(a, t) for _, a, t in links], [("Build status", "https://x/z")])

    def test_resolve_local_detects_a_missing_file_and_a_missing_anchor(self):
        self.assertEqual(resolve_local("README.md", "NO_SUCH_FILE.md"), (False, None))
        self.assertEqual(resolve_local("README.md", "DEPLOY.md#no-such-heading-anywhere"), (True, False))
        self.assertEqual(resolve_local("README.md", "DEPLOY.md#troubleshooting"), (True, True))
        self.assertEqual(resolve_local("README.md", BLOB_PREFIX + "DEPLOY.md#troubleshooting"), (True, True))


if __name__ == "__main__":
    unittest.main()
