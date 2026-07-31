from __future__ import annotations

import hashlib


PUBLIC_SPECTRUM_NAME = "Precise06mv_energy-112.inp"
PUBLIC_SPECTRUM_SHA256 = "184ed63a8e6915a832d84ffb3028d0e3a4135a9b5b8113373a2f078521f1b5f4"
PUBLIC_SPECTRUM_SIZE = 1067
PUBLIC_SPECTRUM_BIN_COUNT = 59
PUBLIC_SPECTRUM_TERMINAL_BOUNDARY_MEV = "6.664"

_PUBLIC_SPECTRUM_ROWS = (
    "0.056\t6.49850E-05",
    "0.168\t1.73950E-04",
    "0.280\t1.97560E-04",
    "0.392\t1.95380E-04",
    "0.504\t2.09060E-04",
    "0.616\t2.15080E-04",
    "0.728\t1.94840E-04",
    "0.840\t1.85520E-04",
    "0.952\t1.75560E-04",
    "1.064\t1.67690E-04",
    "1.176\t1.57490E-04",
    "1.288\t1.48200E-04",
    "1.400\t1.40970E-04",
    "1.512\t1.31630E-04",
    "1.624\t1.23550E-04",
    "1.736\t1.15480E-04",
    "1.848\t1.09660E-04",
    "1.960\t1.02310E-04",
    "2.072\t9.62440E-05",
    "2.184\t9.00640E-05",
    "2.296\t8.60800E-05",
    "2.408\t8.06340E-05",
    "2.520\t7.57700E-05",
    "2.632\t7.13270E-05",
    "2.744\t6.70830E-05",
    "2.856\t6.33480E-05",
    "2.968\t6.03190E-05",
    "3.080\t5.69170E-05",
    "3.192\t5.33090E-05",
    "3.304\t5.04450E-05",
    "3.416\t4.77930E-05",
    "3.528\t4.55400E-05",
    "3.640\t4.28390E-05",
    "3.752\t4.01710E-05",
    "3.864\t3.80090E-05",
    "3.976\t3.66490E-05",
    "4.088\t3.39030E-05",
    "4.200\t3.21100E-05",
    "4.312\t2.97730E-05",
    "4.424\t2.88440E-05",
    "4.536\t2.62690E-05",
    "4.648\t2.50600E-05",
    "4.760\t2.32090E-05",
    "4.872\t2.23940E-05",
    "4.984\t2.03240E-05",
    "5.096\t1.87780E-05",
    "5.208\t1.70480E-05",
    "5.320\t1.60960E-05",
    "5.432\t1.42520E-05",
    "5.544\t1.34480E-05",
    "5.656\t1.17980E-05",
    "5.768\t1.02470E-05",
    "5.880\t8.90850E-06",
    "5.992\t7.37310E-06",
    "6.104\t5.91780E-06",
    "6.216\t4.12700E-06",
    "6.328\t2.48790E-06",
    "6.440\t4.54980E-07",
    "6.552\t0.00000E+00",
    PUBLIC_SPECTRUM_TERMINAL_BOUNDARY_MEV,
)
PUBLIC_SPECTRUM_TEXT = "\n".join(_PUBLIC_SPECTRUM_ROWS)


def public_spectrum_lines() -> tuple[str, ...]:
    payload = PUBLIC_SPECTRUM_TEXT.encode("ascii")
    weighted_rows = _PUBLIC_SPECTRUM_ROWS[:-1]
    if (
        len(payload) != PUBLIC_SPECTRUM_SIZE
        or hashlib.sha256(payload).hexdigest() != PUBLIC_SPECTRUM_SHA256
        or len(weighted_rows) != PUBLIC_SPECTRUM_BIN_COUNT
        or any(len(row.split()) != 2 for row in weighted_rows)
        or _PUBLIC_SPECTRUM_ROWS[-1] != PUBLIC_SPECTRUM_TERMINAL_BOUNDARY_MEV
    ):
        raise RuntimeError("approved public photon spectrum identity is invalid")
    return _PUBLIC_SPECTRUM_ROWS
