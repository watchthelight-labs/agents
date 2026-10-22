#!/usr/bin/env python3
"""
Arithmetic helpers for the compute step. Import from the scratch working file.

    import sys; sys.path.insert(0, str(SKILL / "scripts"))
    from estimate import Q, band, compare, anchors

Nothing here is required. Rule 1 only says do the arithmetic in Python with
units carried explicitly, and plain floats with careful printing satisfy that.
What this buys is that the two things that actually go wrong stop being habits
and become function calls:

  1. A unit slips and the answer is confidently wrong by a factor of a thousand.
     Q multiplies and divides units symbolically, so kg/m2 * 1000 does not
     silently become millimetres — it becomes kg/m2, and the assertion fails.

  2. A number is never compared against anything, so nobody notices it is
     absurd. compare() prints the ratio against a known magnitude and refuses
     to be skipped, because it is the only line that produces the output you
     were going to read anyway.

Run `python estimate.py` for a self-test.
"""

from __future__ import annotations

import math
from collections import Counter

__all__ = ["Q", "band", "compare", "anchors", "ANCHORS", "fmt", "sig"]


# ---- quantities -------------------------------------------------------------

# Derived units expand to SI base on the way in, so J/W reduces to s and a
# watt-second is a joule. Without this the unit engine is only a spell-checker:
# it would reject the one comparison you most want to make.
DERIVED = {
    "N":  {"kg": 1, "m": 1, "s": -2},
    "J":  {"kg": 1, "m": 2, "s": -2},
    "W":  {"kg": 1, "m": 2, "s": -3},
    "Pa": {"kg": 1, "m": -1, "s": -2},
    "Hz": {"s": -1},
    "C":  {"A": 1, "s": 1},
    "V":  {"kg": 1, "m": 2, "s": -3, "A": -1},
    "ohm": {"kg": 1, "m": 2, "s": -3, "A": -2},
    "F":  {"kg": -1, "m": -2, "s": 4, "A": 2},
}
_REVERSE = {frozenset(v.items()): k for k, v in DERIVED.items()}


def _parse(unit):
    """'kg m/s2' -> Counter({'kg': 1, 'm': 1, 's': -2}). Also 'kg*m/s^2'.

    Derived symbols are expanded, so 'J' and 'kg m2/s2' are the same thing and
    compare equal.
    """
    if not unit:
        return Counter()
    num, _, den = unit.replace("*", " ").partition("/")
    out = Counter()
    for part, sign in ((num, 1), (den, -1)):
        for tok in part.split():
            base, _, exp = tok.partition("^")
            if not base:
                continue
            if base[-1].isdigit() and "^" not in tok and not base[:-1].isdigit():
                base, exp = base[:-1], base[-1]     # 's2' -> s^2
            power = sign * int(exp or 1)
            if base in DERIVED:
                for b, p in DERIVED[base].items():
                    out[b] += p * power
            else:
                out[base] += power
    return Counter({k: v for k, v in out.items() if v})


def _combine(a, b, sign):
    """Add or subtract two unit maps.

    Counter's own + and - drop any component that lands at or below zero, which
    silently turns kg / m2 into kg. Exponents have to be allowed to go negative,
    so this does the arithmetic on a plain dict.
    """
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + sign * v
    return Counter({k: v for k, v in out.items() if v})


def _render(c):
    if not c:
        return ""
    named = _REVERSE.get(frozenset(c.items()))
    if named:
        return named
    num = " ".join(k + (str(v) if v != 1 else "")
                   for k, v in sorted(c.items()) if v > 0)
    den = " ".join(k + (str(-v) if v != -1 else "")
                   for k, v in sorted(c.items()) if v < 0)
    if den:
        return f"{num or '1'}/{den}"
    return num


class Q:
    """A number with units that survive arithmetic.

    >>> Q(500, "kg") / Q(1000, "m2")
    Q(0.5, 'kg/m2')
    >>> Q(0.5, "kg/m2") * 1000
    Q(500, 'kg/m2')

    That second line is the whole point. It is the cloud-exemplar error, and it
    comes back wearing its original units instead of quietly becoming a depth.
    """

    __slots__ = ("v", "u")

    def __init__(self, value, unit=""):
        self.v = float(value)
        self.u = _parse(unit) if isinstance(unit, str) else Counter(unit)

    @property
    def unit(self):
        return _render(self.u)

    def _lift(self, o):
        return o if isinstance(o, Q) else Q(o, "")

    def __mul__(self, o):
        o = self._lift(o)
        return Q(self.v * o.v, _combine(self.u, o.u, 1))

    __rmul__ = __mul__

    def __truediv__(self, o):
        o = self._lift(o)
        return Q(self.v / o.v, _combine(self.u, o.u, -1))

    def __rtruediv__(self, o):
        return self._lift(o) / self

    def __add__(self, o):
        o = self._lift(o)
        if self.u != o.u:
            raise ValueError(f"cannot add {self.unit or '1'} to {o.unit or '1'}")
        return Q(self.v + o.v, self.u)

    __radd__ = __add__

    def __sub__(self, o):
        o = self._lift(o)
        if self.u != o.u:
            raise ValueError(
                f"cannot subtract {o.unit or '1'} from {self.unit or '1'}")
        return Q(self.v - o.v, self.u)

    def __rsub__(self, o):
        return self._lift(o) - self

    def __pow__(self, n):
        return Q(self.v ** n, Counter({k: v * n for k, v in self.u.items()}))

    def __neg__(self):
        return Q(-self.v, self.u)

    def __float__(self):
        return self.v

    def __lt__(self, o):
        return self.v < self._lift(o).v

    def __gt__(self, o):
        return self.v > self._lift(o).v

    def to(self, unit):
        """Assert the units are what you think, then hand back the number.

        This is the line to put in front of anything load-bearing. It does not
        convert; it refuses.
        """
        want = _parse(unit)
        if self.u != want:
            raise AssertionError(
                f"unit mismatch: have {self.unit or '1'}, claimed {unit or '1'}")
        return self.v

    def __repr__(self):
        return f"Q({sig(self.v)}, {self.unit!r})"

    def __str__(self):
        return f"{fmt(self.v)} {self.unit}".strip()


def sig(x, n=2):
    """Round to n significant figures. method.md caps the page at two."""
    if x == 0 or not math.isfinite(x):
        return x
    return round(x, -int(math.floor(math.log10(abs(x)))) + (n - 1))


def fmt(x, n=2):
    """Print a number the way the page would: two sig figs, no fake precision."""
    x = sig(x, n)
    if x == 0:
        return "0"
    m = abs(x)
    if m >= 1e5 or m < 1e-3:
        return f"{x:.{n - 1}e}"
    return f"{x:,.0f}" if m >= 100 else f"{x:g}"


# ---- three-point bands ------------------------------------------------------

def band(name, lo, mid, hi, unit=""):
    """Carry an uncertain input as low/central/high and report the spread.

    Deep mode asks for this on every load-bearing input. A chain of point
    estimates hides how much of the answer is a guess; a chain of bands shows
    it, and the spread is often the most interesting number on the page.
    """
    lo, mid, hi = sorted(float(x) for x in (lo, mid, hi))
    ratio = hi / lo if lo else float("inf")
    print(f"  band {name:<26} {fmt(lo)} .. {fmt(mid)} .. {fmt(hi)} {unit}"
          f"   spread x{ratio:.1f}")
    return Q(lo, unit), Q(mid, unit), Q(hi, unit)


# ---- anchors ----------------------------------------------------------------
# Magnitudes a reader already has a feel for. Approximate on purpose: they are
# for smelling out a factor of a thousand, not for use in the chain. Anything
# that reaches the page as a fact still needs its own source.

ANCHORS = {
    "resting human":            (100, "W"),
    "electric kettle":          (2_000, "W"),
    "car engine, cruising":     (20_000, "W"),
    "house, cold night":        (10_000, "W"),
    "sea-level air":            (1.2, "kg/m3"),
    "water":                    (1_000, "kg/m3"),
    "atmosphere overhead":      (10_000, "kg/m2"),
    "adult human":              (70, "kg"),
    "car":                      (1_500, "kg"),
    "loaded lorry":             (40_000, "kg"),
    "blue whale":               (150_000, "kg"),
    "human body water":         (0.042, "m3"),
    "day":                      (86_400, "s"),
    "year":                     (31_500_000, "s"),
    "human lifetime":           (2_500_000_000, "s"),
    "walking pace":             (1.4, "m/s"),
    "motorway speed":           (30, "m/s"),
    "speed of sound in air":    (343, "m/s"),
    "rifle bullet":             (900, "m/s"),
    "low Earth orbit":          (7_800, "m/s"),
    "AA battery":               (10_000, "J"),
    "food calorie":             (4_184, "J"),
    "daily human diet":         (8_400_000, "J"),
    "litre of petrol":          (34_000_000, "J"),
    "atmospheric pressure":     (101_325, "Pa"),
    "car tyre":                 (220_000, "Pa"),
    "people on Earth":          (8_200_000_000, ""),
    "Earth surface area":       (510_000_000_000_000, "m2"),
    "ocean volume":             (1_340_000_000_000_000_000, "m3"),
}


def anchors(unit=None):
    """Print the anchor table, optionally filtered to one unit."""
    for k, (v, u) in ANCHORS.items():
        if unit is None or u == unit:
            print(f"  {k:<26} {fmt(v):>12} {u}")


def compare(label, value, *names, unit=None):
    """Print a quantity beside known magnitudes of the same unit.

    Every load-bearing number goes through here. If the ratio against something
    familiar is absurd, that is visible on this line and nowhere else — which is
    exactly how the one real unit error in this skill's history was eventually
    caught, several hours later, by hand.
    """
    if isinstance(value, Q):
        unit = unit or value.unit
        value = value.v
    unit = unit or ""
    picks = [n for n in names if n in ANCHORS]
    if not picks:
        picks = [k for k, (_, u) in ANCHORS.items() if u == unit]
    print(f"  {label} = {fmt(value)} {unit}".rstrip())
    if not picks:
        print(f"    (no anchor carries {unit or 'that unit'} — "
              f"find something you have a feel for and say so)")
        return
    for n in picks[:4]:
        v, u = ANCHORS[n]
        if not v:
            continue
        r = value / v
        word = f"x{fmt(r)}" if r >= 1 else f"1/{fmt(1 / r)}"
        print(f"    {word:>12} of {n} ({fmt(v)} {u})")


# ---- self-test --------------------------------------------------------------

if __name__ == "__main__":
    print("units survive arithmetic:")
    load = Q(500, "kg") / Q(1_000, "m2")
    print("   ", load, "->", repr(load))
    print("   ", repr(load * 1000), "  <- still kg/m2, not millimetres")
    try:
        (load * 1000).to("mm")
    except AssertionError as exc:
        print("    to('mm') refuses:", exc)
    try:
        Q(1, "kg") + Q(1, "m")
    except ValueError as exc:
        print("    kg + m refuses:", exc)

    print("\nbands:")
    band("liquid water path", 0.03, 0.10, 0.30, "kg/m2")

    print("\nanchors:")
    compare("one person, sustained", Q(6_800, "W"))
    compare("drop at waterjet speed", Q(894, "m/s"))
