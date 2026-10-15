"""Géométrie des deux sources : même distance, angles réglables, mode symétrique."""
from .spatial import wrap


def sep_of(a, b):
    return abs(wrap(a - b))


class Geometry:
    """az_t, az_m : azimuts de la cible et du masqueur (0° = face, +90° = droite)."""

    def __init__(self):
        self.az_t = -45.0
        self.az_m = 45.0
        self.sym = True
        self.snap = 5.0

    @property
    def separation(self):
        return sep_of(self.az_t, self.az_m)

    @property
    def side(self):
        """'L' si la cible est à gauche du droit devant, 'R' si elle est à droite, None si à 0°."""
        return "L" if self.az_t < 0 else ("R" if self.az_t > 0 else None)

    def _snap(self, a):
        s = self.snap or 1.0
        return wrap(round(wrap(a) / s) * s)

    def set_sym(self, sep, side=None):
        """Place les sources symétriquement : séparation `sep` (0–180°), cible du côté `side`."""
        s = self.snap or 1.0
        sep = max(0.0, min(180.0, round(sep / s) * s))
        side = side or self.side or "L"
        h = sep / 2.0
        self.az_t = (-h if side == "L" else h) or 0.0
        self.az_m = (-self.az_t) or 0.0

    def set_az(self, which, a):
        """Déplace une source. En mode symétrique, l'autre prend l'angle opposé (±90° max)."""
        v = self._snap(a)
        if self.sym:
            v = max(-90.0, min(90.0, v))
            other = (-v) or 0.0
            if which == "T":
                self.az_t, self.az_m = v or 0.0, other
            else:
                self.az_m, self.az_t = v or 0.0, other
        elif which == "T":
            self.az_t = v
        else:
            self.az_m = v

    def mirror(self):
        self.az_t = wrap(-self.az_t) or 0.0
        self.az_m = wrap(-self.az_m) or 0.0

    def enable_sym(self):
        self.sym = True
        self.set_sym(self.separation, self.side)
