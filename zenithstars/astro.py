"""Astronomía mínima para ZenithStars v2 — stdlib, sin astropy.

Todos los ángulos en grados salvo que el nombre diga otra cosa; el tiempo
siempre como datetime UTC con zona horaria.

Precisión: precesión IAU 1976 (Lieske) desde J2000. Se omiten nutación
(≤17"), aberración (≤20"), movimiento propio y refracción — suficiente para
dejar una estrella en el campo de colimación, no para astrometría.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

DEG = math.pi / 180.0
ARCSEC = DEG / 3600.0
JD_J2000 = 2451545.0

# ASCOM EquatorialSystem → época a la que hay que llevar las coordenadas.
# None = "de la fecha" (JNow); 1 (topocéntrico) es lo que reportan casi todas
# las monturas. 0 ("other") se trata como de la fecha, que es lo habitual.
EQ_SYSTEMS = {0: 'otro (se asume JNow)', 1: 'topocéntrico (JNow)',
              2: 'J2000', 3: 'J2050', 4: 'B1950'}
_EQ_EPOCH_JD = {2: JD_J2000, 3: JD_J2000 + 50 * 365.25, 4: 2433282.4235}


def julian_date(t: datetime) -> float:
    """JD de un datetime UTC (UT1≈UTC, error <1 s)."""
    if t.tzinfo is None:
        raise ValueError('julian_date necesita un datetime con tzinfo (UTC)')
    return t.timestamp() / 86400.0 + 2440587.5


def gmst(t: datetime) -> float:
    """Tiempo sidéreo medio de Greenwich [deg] (Meeus 12.4, igual que v1)."""
    jd = julian_date(t)
    T = (jd - JD_J2000) / 36525.0
    g = (280.46061837 + 360.98564736629 * (jd - JD_J2000)
         + 0.000387933 * T * T - T * T * T / 38710000.0)
    return g % 360.0


def lst(t: datetime, lon: float) -> float:
    """Tiempo sidéreo local [deg]; lon positiva al Este."""
    return (gmst(t) + lon) % 360.0


# ── vectores y matrices 3×3 ─────────────────────────────────────────────────

def unit_vector(ra: float, dec: float) -> tuple[float, float, float]:
    cd = math.cos(dec * DEG)
    return (cd * math.cos(ra * DEG), cd * math.sin(ra * DEG), math.sin(dec * DEG))


def from_vector(v) -> tuple[float, float]:
    x, y, z = v
    ra = math.atan2(y, x) / DEG % 360.0
    dec = math.asin(max(-1.0, min(1.0, z / math.sqrt(x * x + y * y + z * z)))) / DEG
    return ra, dec


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, s, 0.0), (-s, c, 0.0), (0.0, 0.0, 1.0))


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return ((c, 0.0, -s), (0.0, 1.0, 0.0), (s, 0.0, c))


def _mm(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def rotate(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))


def _transpose(m):
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def precession_matrix(jd: float):
    """P tal que v_época = P · v_J2000 (IAU 1976, Lieske 1977; Meeus 21.2)."""
    T = (jd - JD_J2000) / 36525.0
    zeta = (2306.2181 * T + 0.30188 * T**2 + 0.017998 * T**3) * ARCSEC
    z = (2306.2181 * T + 1.09468 * T**2 + 0.018203 * T**3) * ARCSEC
    theta = (2004.3109 * T - 0.42665 * T**2 - 0.041833 * T**3) * ARCSEC
    return _mm(_rz(-z), _mm(_ry(theta), _rz(-zeta)))


def precess(ra: float, dec: float, jd: float) -> tuple[float, float]:
    """J2000 → equinoccio medio de la época jd."""
    return from_vector(rotate(precession_matrix(jd), unit_vector(ra, dec)))


def unprecess(ra: float, dec: float, jd: float) -> tuple[float, float]:
    """Equinoccio medio de jd → J2000 (inversa de precess)."""
    return from_vector(rotate(_transpose(precession_matrix(jd)), unit_vector(ra, dec)))


def to_mount_system(ra2000: float, dec2000: float, eq_system: int,
                    t: datetime) -> tuple[float, float]:
    """Coordenadas J2000 del catálogo → sistema que declara la montura."""
    jd = _EQ_EPOCH_JD.get(eq_system)
    if jd == JD_J2000:
        return ra2000 % 360.0, dec2000
    return precess(ra2000, dec2000, julian_date(t) if jd is None else jd)


# ── coordenadas horizontales ────────────────────────────────────────────────

def altaz(ha: float, dec: float, lat: float) -> tuple[float, float]:
    """(alt, az) [deg]; az desde el Norte hacia el Este, como v1."""
    h, d, p = ha * DEG, dec * DEG, lat * DEG
    sin_alt = math.sin(d) * math.sin(p) + math.cos(d) * math.cos(p) * math.cos(h)
    alt = math.asin(max(-1.0, min(1.0, sin_alt))) / DEG
    az = math.atan2(-math.cos(d) * math.sin(h),
                    math.sin(d) * math.cos(p) - math.cos(d) * math.sin(p) * math.cos(h))
    return alt, az / DEG % 360.0


def radec_of_altaz(alt: float, az: float, lat: float, lst_deg: float) -> tuple[float, float]:
    """Dirección (alt, az) → (ra, dec) de la fecha [deg]."""
    a, z, p = alt * DEG, az * DEG, lat * DEG
    sin_dec = math.sin(a) * math.sin(p) + math.cos(a) * math.cos(p) * math.cos(z)
    dec = math.asin(max(-1.0, min(1.0, sin_dec))) / DEG
    ha = math.atan2(-math.sin(z) * math.cos(a),
                    math.cos(p) * math.sin(a) - math.sin(p) * math.cos(a) * math.cos(z)) / DEG
    return (lst_deg - ha) % 360.0, dec


def separation(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Distancia angular [deg] (Vincenty, estable a separaciones pequeñas)."""
    d1, d2, dr = dec1 * DEG, dec2 * DEG, (ra2 - ra1) * DEG
    num = math.hypot(math.cos(d2) * math.sin(dr),
                     math.cos(d1) * math.sin(d2) - math.sin(d1) * math.cos(d2) * math.cos(dr))
    den = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(dr)
    return math.atan2(num, den) / DEG


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
