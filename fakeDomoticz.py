"""
Fuller fake Domoticz module + device/image simulation, to actually
exercise plugin.py's onStart()/onHeartbeat() logic (device creation,
multi-region unit allocation, icon wiring) without a real Domoticz
instance. This intentionally does NOT try to fake network calls - tests
using this should monkeypatch meteo.fetchFeed instead.

Since 1.7.2 it is quiet by default and records what the plugin did, so
tests can assert on it:

    fakeDomoticz.messages          list of (level, text) in call order
    fakeDomoticz.errors()          just the Error texts
    fakeDomoticz.Devices[u].history  list of (nValue, sValue, Name) per Update()
    fakeDomoticz.reset()           clear Devices, Images and messages

Set the environment variable FAKEDOMOTICZ_VERBOSE=1 to also print every
message and device update.
"""
import os
import zipfile

VERBOSE = os.environ.get("FAKEDOMOTICZ_VERBOSE", "") not in ("", "0")

messages = []


def _record(level, msg):
    messages.append((level, str(msg)))
    if VERBOSE:
        print("[{}]".format(level), msg)


def Debug(msg):
    _record("DEBUG", msg)


def Log(msg):
    _record("LOG", msg)


def Error(msg):
    _record("ERROR", msg)


def errors():
    return [text for level, text in messages if level == "ERROR"]


def Debugging(level):
    pass


class FakeImageHandle:
    def __init__(self, name, image_id):
        self.Name = name
        self.ID = image_id

    def Create(self):
        # Like Domoticz, expect icons.txt at the ROOT of the zip - a zip
        # packed with a subfolder (or macOS extras around it) fails here.
        with zipfile.ZipFile(self._filename) as zf:
            with zf.open('icons.txt') as f:
                lines = f.read().decode('utf-8').strip().splitlines()
        next_id = len(Images) + 1
        for line in lines:
            name = line.split(';')[0]
            if name not in Images:
                Images[name] = FakeImageHandle(name, next_id)
                next_id += 1
        return self


def Image(Filename):
    h = FakeImageHandle(Filename, None)
    h._filename = Filename
    return h


class FakeDevice:
    def __init__(self, Name, Unit, TypeName, Used=1):
        self.Name = Name
        self.Unit = Unit
        self.TypeName = TypeName
        self.Used = Used
        self.nValue = 0
        self.sValue = ""
        self.ID = Unit
        self.LastLevel = 0
        self.LastImage = None
        self.history = []
        self._created = False

    def Create(self):
        Devices[self.Unit] = self
        self._created = True
        return self

    def Update(self, nValue, sValue, Name=None, Image=None):
        self.nValue = nValue
        self.sValue = sValue
        self.history.append((nValue, sValue, Name))
        if Name is not None:
            self.Name = Name
        if Image is not None:
            self.LastImage = Image
        if VERBOSE:
            print("    -> Unit {}: nValue={} sValue={!r} Name={!r} Image={}"
                  .format(self.Unit, nValue, sValue, self.Name, Image))


def Device(Name, Unit, TypeName, Used=1):
    return FakeDevice(Name, Unit, TypeName, Used)


Devices = {}
Images = {}


def reset():
    """clear all recorded state between tests (keeps the same dict objects,
    which plugin.py holds references to)."""
    Devices.clear()
    Images.clear()
    del messages[:]
