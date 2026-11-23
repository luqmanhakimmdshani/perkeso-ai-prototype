"""PERKESO monthly contribution for an employed worker. Single source of truth for the calculator tab AND the chat tool.

Exact official schedules (perkeso.gov.my, Nov 2026):
- Act 4 incl. LINDUNG 24 Jam (SKBBK): kb/akta4.json, parsed from JadualCarumanBaharuTermasukSKBBK.pdf (65 wage bands).
- Act 800 (SIP): 0.2% of the RM100 band midpoint, fixed amounts below RM200, read from kb/akta800.pdf.
ponytail: the Act 4 PDF prices LINDUNG 24 Jam at Phase 1 (0.75%, until 31 May 2028). From Phase 2 the code falls back to
rate x band midpoint as an estimate; replace kb/akta4.json with the new schedule when PERKESO publishes it.
"""
import json, math, os
from datetime import date

SILING = 6000.0  # wage ceiling since 1 Oct 2024
L24_MULA = date(2026, 6, 1)
SIP_RENDAH = [(30, 0.05), (50, 0.10), (70, 0.15), (100, 0.20), (140, 0.25), (200, 0.35)]  # Akta 800 rows 1-6
AKTA4 = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "kb", "akta4.json")))


def kadar_l24(hari=None):
    """LINDUNG 24 Jam employee rate: 0.75% years 1-2, 1.00% years 3-5, 1.25% from year 6."""
    tahun = ((hari or date.today()) - L24_MULA).days // 365 + 1
    return 0.0075 if tahun <= 2 else 0.010 if tahun <= 5 else 0.0125


def asas_jalur(gaji):
    """Midpoint of the RM100 band ('melebihi RMx tetapi tidak melebihi RMx+100'), capped at the RM5,950 band."""
    return min(math.ceil(gaji / 100) * 100 - 50, SILING - 50) if gaji > 0 else 0.0


def sip(gaji):
    """Exact Akta 800 amount per side (employer = employee)."""
    for had, amaun in SIP_RENDAH:
        if gaji <= had:
            return amaun
    return round(asas_jalur(gaji) * 0.002, 2)


def jalur_akta4(gaji):
    """Row of the Act 4 schedule: first band whose upper limit covers the wage; above RM6,000 -> last row."""
    return next((r for r in AKTA4 if gaji <= r["had"]), AKTA4[-1])


def kira_caruman(gaji, kategori, umur_60_ke_atas=False, lindung24=None):
    """kategori: 'tempatan' (citizen/PR, incl. local domestic workers) or 'asing' (foreign, incl. foreign domestic).
    lindung24: voluntary for locals (default off), mandatory for foreign workers."""
    if kategori == "domestik":  # older callers: local domestic workers follow local rates
        kategori = "tempatan"
    if kategori not in ("tempatan", "asing") or gaji < 0:
        raise ValueError("kategori mesti 'tempatan' atau 'asing', gaji >= 0")
    g = float(gaji)
    r = jalur_akta4(g)
    asing = kategori == "asing"
    l24 = True if asing else bool(lindung24)
    if umur_60_ke_atas:  # Jenis Kedua
        butiran = [{"skim": "Skim Bencana Pekerjaan", "majikan": r["j2_majikan"], "pekerja": 0.0}]
    else:                # Jenis Pertama: employer share covers Bencana Pekerjaan + Keilatan
        butiran = [{"skim": "Skim Bencana Pekerjaan & Keilatan", "majikan": r["j1_majikan"], "pekerja": r["j1_keilatan"]}]
        if not asing:
            s = sip(g)
            butiran.append({"skim": "Insurans Pekerjaan (SIP)", "majikan": s, "pekerja": s})
    nota = ["Mengikut Jadual Caruman rasmi Akta 4 dan Akta 800."]
    if l24:
        if kadar_l24() == 0.0075:
            l24_amaun = r["j2_l24"] if umur_60_ke_atas else r["j1_l24"]
        else:
            l24_amaun = round(asas_jalur(g) * kadar_l24(), 2)
            nota.append(f"LINDUNG 24 Jam kini {kadar_l24():.2%}; amaun ialah anggaran sehingga jadual baharu diterbitkan.")
        butiran.append({"skim": "LINDUNG 24 Jam", "majikan": 0.0, "pekerja": l24_amaun})
    if g > SILING:
        nota.append(f"Gaji melebihi had siling RM{SILING:,.0f}; caruman mengikut kadar maksimum.")
    if umur_60_ke_atas:
        nota.append("Pekerja 60 tahun ke atas: Caruman Jenis Kedua (tiada Keilatan dan SIP).")
    if not asing and not l24:
        nota.append("LINDUNG 24 Jam adalah sukarela bagi pekerja tempatan (tidak termasuk dalam kiraan ini).")
    return {
        "butiran": butiran,
        "jumlah_majikan": round(sum(b["majikan"] for b in butiran), 2),
        "jumlah_pekerja": round(sum(b["pekerja"] for b in butiran), 2),
        "nota": " ".join(nota),
        "sumber": "https://www.perkeso.gov.my/perkhidmatan-kami/majikan-pekerja/kadar-caruman.html",
    }


if __name__ == "__main__":  # self-check: python caruman.py
    # Akta 800 rows straight from kb/akta800.pdf
    for w, amt in [(30, .05), (45, .10), (100, .20), (150, .35), (250, .50), (300, .50), (300.01, .70),
                   (999, 1.90), (3050, 6.10), (5000, 9.90), (5950, 11.90), (6000, 11.90), (9000, 11.90)]:
        assert sip(w) == amt, (w, sip(w), amt)
    # Akta 4 rows from kb/akta4.pdf (row 34: RM2,900-3,000; row 35: RM3,000-3,100; row 65: above RM6,000)
    assert len(AKTA4) == 65 and all(a["had"] <= b["had"] for a, b in zip(AKTA4, AKTA4[1:]))
    r = kira_caruman(3000, "tempatan")
    assert (r["jumlah_majikan"], r["jumlah_pekerja"]) == (round(51.65 + 5.90, 2), round(14.75 + 5.90, 2)), r
    r = kira_caruman(3000.01, "tempatan", lindung24=True)
    assert r["butiran"][0]["majikan"] == 53.35 and r["butiran"][-1]["pekerja"] == 22.85, r
    r = kira_caruman(9000, "tempatan")
    assert r["butiran"][0]["majikan"] == 104.15 and r["butiran"][1]["majikan"] == 11.90, r
    r = kira_caruman(3050, "tempatan", umur_60_ke_atas=True)
    assert (r["jumlah_majikan"], r["jumlah_pekerja"]) == (38.10, 0.0), r       # Jenis Kedua, row 35
    r = kira_caruman(3050, "asing")                                           # Jenis Pertama + mandatory L24, no SIP
    assert (r["jumlah_majikan"], r["jumlah_pekerja"]) == (53.35, round(15.25 + 22.85, 2)), r
    assert not any(b["skim"].startswith("Insurans") for b in r["butiran"])
    assert kadar_l24(date(2026, 6, 1)) == 0.0075 and kadar_l24(date(2029, 1, 1)) == 0.01 and kadar_l24(date(2032, 6, 2)) == 0.0125
    print("ok")
