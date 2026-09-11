"""
Fuller fake Domoticz module + device/image simulation, to actually
exercise plugin.py's onStart()/onHeartbeat() logic (device creation,
multi-region unit allocation, icon wiring) without a real Domoticz
instance. This intentionally does NOT try to fake network calls - tests
using this should monkeypatch meteo.fetchFeed instead.
"""


def Debug(msg):
    print("[DEBUG]", msg)


def Log(msg):
    print("[LOG]", msg)


def Error(msg):
    print("[ERROR]", msg)


def Debugging(level):
    pass


class FakeImageHandle:
    def __init__(self, name, image_id):
        self.Name = name
        self.ID = image_id

    def Create(self):
        import zipfile
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
        self._created = False

    def Create(self):
        Devices[self.Unit] = self
        self._created = True
        return self

    def Update(self, nValue, sValue, Name=None, Image=None):
        self.nValue = nValue
        self.sValue = sValue
        if Name is not None:
            self.Name = Name
        if Image is not None:
            self.LastImage = Image
        print("    -> Unit {}: nValue={} sValue={!r} Name={!r} Image={}"
              .format(self.Unit, nValue, sValue, self.Name, Image))


def Device(Name, Unit, TypeName, Used=1):
    return FakeDevice(Name, Unit, TypeName, Used)


Devices = {}
Images = {}

