from __future__ import annotations

from decimal import Decimal

import pytest

from dicomxphits.machine_config import public_default_machine_config
from dicomxphits.public_dose_contract import (
    PUBLIC_MODEL_D_PHITS_REFERENCE_GY_PER_SOURCE,
    PUBLIC_MODEL_MACHINE_CONFIG_SHA256,
    PUBLIC_MODEL_TOTFACT_PER_MU,
    PUBLIC_MODEL_TOTFACT_PER_MU_UNROUNDED,
    StalePublicDoseFactorError,
    approved_public_model_calibration,
    machine_config_sha256,
)


def test_approved_public_factor_preserves_derivation_and_rounding():
    assert (
        Decimal("0.0078308") / PUBLIC_MODEL_D_PHITS_REFERENCE_GY_PER_SOURCE
        == PUBLIC_MODEL_TOTFACT_PER_MU_UNROUNDED
    )
    assert PUBLIC_MODEL_TOTFACT_PER_MU == Decimal("8.7608E+11")


def test_approved_public_factor_matches_built_in_model_identity():
    machine_config = public_default_machine_config()

    calibration = approved_public_model_calibration(machine_config)

    assert machine_config_sha256(machine_config) == (
        PUBLIC_MODEL_MACHINE_CONFIG_SHA256
    )
    assert calibration["totfact_per_mu"] == "8.7608E+11"
    assert calibration["units"] == "source/MU"


def test_approved_public_factor_rejects_changed_model_as_stale():
    machine_config = public_default_machine_config()
    machine_config["source"]["width_x_mm"] = 3.001

    with pytest.raises(StalePublicDoseFactorError, match="stale"):
        approved_public_model_calibration(machine_config)
