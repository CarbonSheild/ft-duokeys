# ft-duokeys

A VR keyboard for the Steam Frame that both controllers type on at once. SteamVR's own keyboard follows one laser at a time; this one draws a ray, cursor and highlight for each hand, and either hand's trigger or bumper presses the key under its ray.

Keys go out through a virtual USB keyboard (uinput). With Frametop installed, its input relay treats it like any other keyboard, so typing goes wherever you last clicked: the Frametop desktop or Steam's side.

## Install

```
./install.sh
```

This makes a Python venv in this folder (pyopenvr and Pillow) and installs a systemd user service that starts and stops with SteamVR. Nothing outside your home folder changes. `./install.sh uninstall` removes the service.

## Use

| Do this | To get this |
| --- | --- |
| Press both grips together | Open the keyboard in front of you, or close it |
| Point at a key, pull the trigger or the bumper | Type it (each hand on its own; a short buzz per key) |
| Tap Shift, Ctrl, Alt or Meta | It stays on for the next key (it lights up); tap again to drop it |
| Hold Shift with one hand | Type shifted with the other |
| Hold a trigger on the bar at the top, and move | Carry the keyboard; let go to put it down. It opens there from then on (as seen from your head, so in front of wherever you face) |
| Close key | Close it |

While a VR game runs, the grips combination is off, so it can't open in the middle of a game, and the keyboard closes if one starts. `ft-duokeys toggle` (or `show`, `hide`, `status`, and `reset-place` to forget where you put it) works from a terminal at any time:

```
.venv/bin/python ft-duokeys toggle
```

Typing follows Frametop's idea of where you last clicked. It only sees clicks on its desktop screens and the mouse's clicks elsewhere, so after clicking into Steam's interface with a controller, keys still go to the desktop window that had them. That's Frametop's routing (a physical keyboard does the same), not something this keyboard can see.

If Frametop's own keyboard opens by itself on text fields, set it to open only from its button (Frametop Input Settings → Keyboard), or SteamVR's laser can land on it instead.

Logs: `journalctl --user -u ft-duokeys -f`. To try changes by hand, stop the service and run `.venv/bin/python ft-duokeys --show --log-hits`.

## How it works, and what didn't

SteamOS on the Frame (October 2026) shaped most of this:

- **Triggers come from vrserver's web socket** (`vrws.py`, from Frametop), the same live view SteamVR's controller binding page uses. It works without input focus and takes nothing from anyone. The analog trigger value is used rather than the click: quick pulls often lost their click between two of vrserver's batches. A long-lived subscription has gone quiet before, so it's renewed every 5 seconds.
- **SteamVR's clicks are absorbed.** The panel is a mouse-input overlay, so SteamVR's laser lands on it and its click doesn't reach the window behind. The clicks don't type: SteamVR's laser follows one hand, so the first pull after switching hands only moves it.
- **Per-hand button takeover doesn't work** (`--take`). It needs "Enable global input from overlays" (`steamvr/globalActionSetPriority`), and with it on, SteamVR still delivers nothing to overlay-global action sets when no game is running, even after a restart. Frametop's controller button mapping uses the same mechanism and also got nothing. It's kept behind `--take`, with a fallback, in case it works in games or a later SteamVR.
- **The panel is never redrawn while typing.** SteamVR takes 201 `SetOverlayRaw` uploads from a process and refuses the rest. `SetOverlayFromFile` loads in the background (a blank moment each time) and caches by file name. So the plain and shifted panels are each drawn once, as two overlays that Shift switches between, and hover, press and held-modifier highlights are small overlays moved over the keys.
- **Haptics** use the legacy `TriggerHapticPulse`: the haptic action needs input focus that an overlay doesn't have.

## Files

- `ft-duokeys`: the app (overlays, rays, triggers, typing)
- `layout.py`: the keys, and how presses become key events (modifiers, two hands)
- `hands.py`: ray casting, placement, the takeover rule
- `render.py`: drawing (Pillow)
- `uinput.py`: the virtual keyboard
- `vrws.py`: vrserver's web socket (copied from Frametop, MIT)
- `actions/`: the action manifest and bindings for `--take`
- `test/test_offline.py`: tests that need no headset (`python3 test/test_offline.py`)

## License

MIT (see `LICENSE`). `vrws.py` comes from [Frametop](https://github.com/Frametop/frametop), also MIT.
