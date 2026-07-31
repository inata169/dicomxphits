from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any, Mapping

from dicomxphits.public_spectrum import PUBLIC_SPECTRUM_SHA256


PUBLIC_MODEL_D_PHITS_REFERENCE_GY_PER_SOURCE = Decimal(
    "8.938433333333334E-15"
)
PUBLIC_MODEL_TOTFACT_PER_MU_UNROUNDED = (
    Decimal("0.0078308") / PUBLIC_MODEL_D_PHITS_REFERENCE_GY_PER_SOURCE
)
PUBLIC_MODEL_TOTFACT_PER_MU = Decimal("8.7608E+11")
PUBLIC_MODEL_TOTFACT_PER_MU_TEXT = "8.7608E+11"
PUBLIC_MODEL_MACHINE_CONFIG_SHA256 = (
    "525fe859a611af63b2662ae1fb90841a804d080c2cda21f56c72c559157b1a61"
)
PUBLIC_MODEL_CALIBRATION_EVIDENCE_SHA256 = (
    "0fdd11a51be3f487f180ed2fd5cffaad84d1943621ec86e76462fc1e8e65e587"
)


class StalePublicDoseFactorError(ValueError):
    """Raised when the approved factor is requested for a different model."""


def machine_config_sha256(machine_config: Mapping[str, Any]) -> str:
    payload = json.dumps(
        machine_config,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def approved_public_model_calibration(
    machine_config: Mapping[str, Any],
) -> dict[str, Any]:
    actual_machine_hash = machine_config_sha256(machine_config)
    if actual_machine_hash != PUBLIC_MODEL_MACHINE_CONFIG_SHA256:
        raise StalePublicDoseFactorError(
            "approved totfact_per_MU is stale for this machine config; "
            f"expected {PUBLIC_MODEL_MACHINE_CONFIG_SHA256}, "
            f"got {actual_machine_hash}"
        )
    return {
        "status": "human_accepted",
        "totfact_per_mu": PUBLIC_MODEL_TOTFACT_PER_MU_TEXT,
        "units": "source/MU",
        "machine_config_sha256": actual_machine_hash,
        "spectrum_sha256": PUBLIC_SPECTRUM_SHA256,
        "evidence_sha256": PUBLIC_MODEL_CALIBRATION_EVIDENCE_SHA256,
        "human_accepted_on": "2026-07-30",
        "accepted_batches": 84,
        "accepted_histories": 1_680_000_000,
    }
