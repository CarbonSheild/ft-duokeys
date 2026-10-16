"""A virtual keyboard through /dev/uinput, with nothing but the standard library (the
SteamOS host has no compiler to build python-evdev, and Frametop's input relay does the
same).

Where its keys go: gamescope reads every input device itself and types into Steam's side
(the dashboard, Steam, a game). The Frametop desktop is a nested KWin that reads no
devices at all; Frametop's input relay forwards pass-through keyboards to it (ft-screens)
while typing goes to the desktop, and grabs them meanwhile so gamescope doesn't type the
same keys. The relay only takes USB and Bluetooth keyboards, so this one says it's USB:
then it's one more pass-through keyboard, and typing follows the last click like a real
one. (It counts as a program's keyboard, not a real one, for when Frametop's own keyboard
opens, since it lives under /sys/devices/virtual.)
"""
import fcntl
import os
import struct
import time

EV_SYN, EV_KEY = 0x00, 0x01
SYN_REPORT = 0
BUS_USB = 0x03
EVENT = struct.Struct("llHHi")


def _ioc(direction, nr, size, kind):
    return (direction << 30) | (size << 16) | (ord(kind) << 8) | nr


UI_DEV_CREATE = _ioc(0, 1, 0, "U")
UI_DEV_DESTROY = _ioc(0, 2, 0, "U")
UI_DEV_SETUP = _ioc(1, 3, 92, "U")  # struct uinput_setup: input_id (4 x u16), name[80], u32 ff_effects_max
UI_SET_EVBIT = _ioc(1, 100, 4, "U")
UI_SET_KEYBIT = _ioc(1, 101, 4, "U")

NAME = "ft-duokeys keyboard"


class Keyboard:
    def __init__(self, name=NAME, codes=range(1, 0x100)):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            for code in codes:
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            # No vendor or product: the relay knows a USB device by bus:vendor:product:name,
            # so the fixed name is what lets Frametop Input Settings remember its role.
            setup = struct.pack("HHHH80sI", BUS_USB, 0, 0, 1, name.encode()[:79], 0)
            fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except BaseException:
            os.close(self.fd)
            raise
        self.down = set()

    def send(self, code, value):
        t = time.time()
        sec, usec = int(t), int((t % 1) * 1e6)
        os.write(self.fd, EVENT.pack(sec, usec, EV_KEY, code, value) + EVENT.pack(sec, usec, EV_SYN, SYN_REPORT, 0))
        if value:
            self.down.add(code)
        else:
            self.down.discard(code)

    def close(self):
        for code in sorted(self.down):
            try:
                self.send(code, 0)
            except OSError:
                pass
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        finally:
            os.close(self.fd)
