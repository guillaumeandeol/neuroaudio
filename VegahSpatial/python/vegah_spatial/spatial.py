"""Spatialisation binaurale (HRTF KEMAR, plan horizontal) et mixage d'un essai.

Convention d'angle : 0° = droit devant, +90° = droite, -90° = gauche, 180° = derrière.
Les HRIR (MIT KEMAR, Gardner & Martin 1994, pavillon normal) sont mesurées tous les 5° ;
les angles intermédiaires sont obtenus en interpolant les réponses après alignement de leur
retard d'attaque (le retard interaural est interpolé séparément, pour éviter les peignes).
"""
import os
import numpy as np
from math import gcd
from scipy.signal import fftconvolve, resample_poly

FS = 44100
REF_RMS = 0.05            # RMS de référence de chaque phrase (-26 dBFS) avant niveau général
PEAK_MAX = 0.98
_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "kemar_horizontal.npz")


def wrap(a):
    """Ramène un angle dans ]-180, 180]."""
    a = (float(a) + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a


def _frac_shift(h, d, n):
    """Décale h (1-D) de d échantillons (fractionnaire) par rotation de phase ; sortie de longueur n."""
    nfft = 1 << int(np.ceil(np.log2(n + 8)))
    spec = np.fft.rfft(h, nfft)
    f = np.fft.rfftfreq(nfft)
    return np.fft.irfft(spec * np.exp(-2j * np.pi * f * d), nfft)[:n]


def _onset(h, frac=0.2):
    """Retard d'attaque (échantillons, sous-échantillon) : premier franchissement de frac*pic."""
    a = np.abs(h)
    thr = frac * a.max()
    i = int(np.argmax(a >= thr))
    if i == 0:
        return 0.0
    return (i - 1) + (thr - a[i - 1]) / max(a[i] - a[i - 1], 1e-12)


class HRTF:
    def __init__(self, path=_DATA):
        z = np.load(path)
        az = z["azimuth"].astype(float)
        o = np.argsort(az)
        self.az = az[o]
        self.hrir = z["hrir"][o].astype(float)            # (N, taps, 2) : colonnes gauche, droite
        self.fs = int(z["fs"])
        self.step = 360.0 / len(self.az)
        n, taps, _ = self.hrir.shape
        self.out_taps = taps + 96
        self.delay = np.zeros((n, 2))
        self.aligned = np.zeros_like(self.hrir)
        for i in range(n):
            for e in range(2):
                d = _onset(self.hrir[i, :, e])
                self.delay[i, e] = d
                self.aligned[i, :, e] = _frac_shift(self.hrir[i, :, e], -d, taps)
        self._cache = {}

    def at(self, azimuth):
        """HRIR (taps, 2) pour un azimut quelconque (interpolée)."""
        a = wrap(azimuth)
        key = round(a, 3)
        if key in self._cache:
            return self._cache[key]
        p = (a - self.az[0]) / self.step
        i0 = int(np.floor(p)) % len(self.az)
        i1 = (i0 + 1) % len(self.az)
        w = p - np.floor(p)
        out = np.zeros((self.out_taps, 2))
        for e in range(2):
            h = (1 - w) * self.aligned[i0, :, e] + w * self.aligned[i1, :, e]
            d = (1 - w) * self.delay[i0, e] + w * self.delay[i1, e]
            out[:, e] = _frac_shift(h, d, self.out_taps)
        self._cache[key] = out
        return out


_hrtf = None


def get_hrtf():
    global _hrtf
    if _hrtf is None:
        _hrtf = HRTF()
    return _hrtf


def to_fs(x, fs_in, fs_out=FS):
    if fs_in == fs_out:
        return x
    g = gcd(int(fs_in), int(fs_out))
    return resample_poly(x, fs_out // g, fs_in // g)


def binaural(x, azimuth, hrtf=None):
    """Spatialise un signal mono (FS) à l'azimut donné → tableau (n, 2)."""
    h = (hrtf or get_hrtf()).at(azimuth)
    return np.stack([fftconvolve(x, h[:, 0]), fftconvolve(x, h[:, 1])], axis=1)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) or 1e-9


def render_trial(target, masker, az_t, az_m, snr_db=0.0, lead_s=0.0, master_db=0.0,
                 loop_masker=True, hrtf=None):
    """Mixe cible et masqueur spatialisés.

    SNR = niveau RMS de la cible moins celui du masqueur, mesurés sur les signaux d'origine
    (avant spatialisation) ; chaque phrase est d'abord ramenée au RMS de référence.
    Renvoie (signal float32 (n, 2), infos).
    """
    master = 10 ** (master_db / 20.0)
    g_t = REF_RMS / rms(target) * master
    g_m = REF_RMS / rms(target if masker is None else masker) * master * 10 ** (-snr_db / 20.0)
    lead = int(round(max(0.0, lead_s) * FS))
    end_t = lead + len(target)
    m = masker
    if loop_masker and len(m) < end_t:
        reps = int(np.ceil(end_t / len(m)))
        m = np.tile(m, reps)[:end_t + int(0.05 * FS)]
    y_t = binaural(target * g_t, az_t, hrtf)
    y_m = binaural(m * g_m, az_m, hrtf)
    n = max(lead + len(y_t), len(y_m))
    out = np.zeros((n, 2))
    out[:len(y_m)] += y_m
    out[lead:lead + len(y_t)] += y_t
    peak = float(np.abs(out).max())
    limit_db = 0.0
    if peak > PEAK_MAX:
        k = PEAK_MAX / peak
        out *= k
        limit_db = -20 * np.log10(k)
    return out.astype(np.float32), {"limit_db": limit_db, "duration": n / FS, "peak": min(peak, PEAK_MAX)}


def test_bursts(az_t, az_m, master_db=0.0, hrtf=None):
    """Test sans corpus : 3 salves de bruit à l'angle de la cible, puis 2 salves longues à celui du masqueur."""
    rng = np.random.default_rng(0)

    def burst(pattern):
        total = pattern[-1][0] + pattern[-1][1] + 0.05
        x = np.zeros(int(total * FS))
        lp = 0.0
        for s0, du in pattern:
            i0, i1 = int(s0 * FS), int((s0 + du) * FS)
            r = int(0.01 * FS)
            seg = np.zeros(i1 - i0)
            for k in range(len(seg)):
                lp = 0.7 * lp + 0.3 * (rng.random() * 2 - 1)
                seg[k] = lp
            env = np.minimum(1.0, np.minimum(np.arange(len(seg)) / r, (len(seg) - np.arange(len(seg))) / r))
            x[i0:i1] = seg * 0.5 * env
        return x

    g = 0.6 * 10 ** (master_db / 20.0)
    a = binaural(burst([(0, .25), (.4, .25), (.8, .25)]) * g, az_t, hrtf)
    b = binaural(burst([(0, .6), (.8, .6)]) * g, az_m, hrtf)
    gap = np.zeros((int(0.4 * FS), 2))
    out = np.concatenate([a, gap, b])
    pk = float(np.abs(out).max())
    if pk > PEAK_MAX:
        out *= PEAK_MAX / pk
    return out.astype(np.float32)
