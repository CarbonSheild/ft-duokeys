"""Ray casting onto the keyboard panel, and when to take a hand's buttons.

Poses are 3x4 row-major matrices as nested lists (OpenVR's HmdMatrix34_t layout): columns
0-2 are the x, y, z axes, column 3 the position. An overlay's front faces its +z, and a
laser aims along its own -z.
"""
import math


def mul(a, b):
    """a * b for 3x4 rigid transforms."""
    return [[sum(a[i][k] * b[k][j] for k in range(3)) + (a[i][3] if j == 3 else 0.0) for j in range(4)]
            for i in range(3)]


def inverse(m):
    """The inverse of a rigid 3x4 transform: R^T and -R^T t."""
    rt = [[m[j][i] for j in range(3)] for i in range(3)]
    t = [-sum(rt[i][k] * m[k][3] for k in range(3)) for i in range(3)]
    return [rt[i] + [t[i]] for i in range(3)]


def col(m, j):
    return (m[0][j], m[1][j], m[2][j])


def to_local(m, p):
    """Point p (world) in m's frame, for a rigid m: R^T (p - t)."""
    d = (p[0] - m[0][3], p[1] - m[1][3], p[2] - m[2][3])
    return tuple(sum(m[i][j] * d[i] for i in range(3)) for j in range(3))


def dir_local(m, v):
    return tuple(sum(m[i][j] * v[i] for i in range(3)) for j in range(3))


def ray_hit(panel, width, height, laser):
    """Where a laser meets the panel's plane, as (x, y, distance) with x and y in metres
    from its top left corner (y down), or None if the laser points away from its front.
    Hits outside the panel are returned too; the caller decides how much margin counts."""
    o = to_local(panel, col(laser, 3))
    z = col(laser, 2)
    d = dir_local(panel, (-z[0], -z[1], -z[2]))
    if o[2] <= 0 or d[2] >= -1e-6:
        return None  # behind the panel, or aiming parallel to it or away
    t = -o[2] / d[2]
    x, y = o[0] + t * d[0], o[1] + t * d[1]
    return x + width / 2, height / 2 - y, t


def inside(hit, width, height, margin=0.0):
    return hit is not None and -margin <= hit[0] <= width + margin and -margin <= hit[1] <= height + margin


class Takeover:
    """Whether one hand's buttons are ours. Taken when its ray is on the keyboard with the
    trigger up, given back when it leaves with the trigger up; never while the trigger is
    held, which would leave a button stuck down in whichever app had the press. Once taken,
    the panel counts as `grow` metres bigger, so the edge doesn't flicker."""

    def __init__(self, grow=0.015):
        self.grow = grow
        self.taken = False

    def update(self, hit, width, height, trigger_down, want=True):
        """want: the keyboard is open. Returns whether the hand is taken now."""
        hitting = want and inside(hit, width, height, self.grow if self.taken else 0.0)
        if not trigger_down and hitting != self.taken:
            self.taken = hitting
        return self.taken


def yaw_frame(head):
    """The head's position, turned only as far as it faces around the room: level, so a
    panel placed in it doesn't tip with the head."""
    fx, fz = -head[0][2], -head[2][2]  # the head's forward, flattened
    n = math.hypot(fx, fz)
    if n < 1e-3:
        fx, fz = 0.0, -1.0
    else:
        fx, fz = fx / n, fz / n
    yaw = math.atan2(-fx, -fz)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return [[cy, 0.0, sy, head[0][3]], [0.0, 1.0, 0.0, head[1][3]], [-sy, 0.0, cy, head[2][3]]]


def default_offset(distance=0.55, drop=0.38, tilt_deg=35.0):
    """The panel in the head's yaw frame: `distance` ahead, `drop` below the eyes, tipped
    back by `tilt_deg` (its top leans away) to face them."""
    t = math.radians(tilt_deg)
    ct, st = math.cos(t), math.sin(t)
    return [[1.0, 0.0, 0.0, 0.0], [0.0, ct, st, -drop], [0.0, -st, ct, -distance]]


def placement(head, offset=None):
    """A panel pose in front of the head: `offset` (default_offset() if None) in its yaw
    frame. A carried panel's offset is remember(head, its pose)."""
    return mul(yaw_frame(head), offset or default_offset())


def remember(head, pose):
    """The offset that places `pose` again, in front of wherever the head faces then."""
    return mul(inverse(yaw_frame(head)), pose)


def laser_pose(origin, end, head, length):
    """A pose for a thin laser quad from origin to end: its y axis along the beam, its
    front turned toward the head as far as the beam allows; centred halfway."""
    d = [end[i] - origin[i] for i in range(3)]
    n = math.sqrt(sum(c * c for c in d)) or 1.0
    y = [c / n for c in d]
    mid = [origin[i] + d[i] / 2 for i in range(3)]
    to_head = [head[i] - mid[i] for i in range(3)]
    dot = sum(to_head[i] * y[i] for i in range(3))
    z = [to_head[i] - dot * y[i] for i in range(3)]
    zn = math.sqrt(sum(c * c for c in z))
    if zn < 1e-6:
        z = [0.0, 0.0, 1.0] if abs(y[2]) < 0.9 else [1.0, 0.0, 0.0]
        dot = sum(z[i] * y[i] for i in range(3))
        z = [z[i] - dot * y[i] for i in range(3)]
        zn = math.sqrt(sum(c * c for c in z))
    z = [c / zn for c in z]
    x = [y[1] * z[2] - y[2] * z[1], y[2] * z[0] - y[0] * z[2], y[0] * z[1] - y[1] * z[0]]
    return [[x[i], y[i], z[i], mid[i]] for i in range(3)]
