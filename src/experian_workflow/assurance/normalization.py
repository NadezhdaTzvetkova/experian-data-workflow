from __future__ import annotations

import pandas as pd


class CanonicalMappingError(ValueError):
    pass


def normalize_control_evidence_identity(
    evidence: pd.DataFrame,
    system_mappings: pd.DataFrame,
    *,
    mapping_source_system: str,
) -> pd.DataFrame:
    required_evidence = {
        "test_id",
        "raw_system_id",
    }
    required_mappings = {
        "source_system",
        "raw_system_id",
        "canonical_system_id",
        "mapping_status",
    }

    missing_evidence = sorted(required_evidence - set(evidence.columns))
    if missing_evidence:
        raise CanonicalMappingError(
            "Control evidence is missing identity prerequisites: "
            + ", ".join(missing_evidence)
        )

    missing_mappings = sorted(
        required_mappings - set(system_mappings.columns)
    )
    if missing_mappings:
        raise CanonicalMappingError(
            "System mappings are missing identity prerequisites: "
            + ", ".join(missing_mappings)
        )

    raw_system_id_text = evidence["raw_system_id"].astype("string")
    invalid_evidence_identity_mask = (
        raw_system_id_text.isna()
        | raw_system_id_text.str.strip().eq("")
    )
    if invalid_evidence_identity_mask.any():
        affected = tuple(
            evidence.index[
                invalid_evidence_identity_mask
            ].astype(str)
        )
        raise CanonicalMappingError(
            "Control evidence contains missing or blank raw_system_id "
            "values at row indexes: "
            + ", ".join(affected)
        )

    scoped_mappings = system_mappings.loc[
        system_mappings["source_system"] == mapping_source_system,
        [
            "raw_system_id",
            "canonical_system_id",
            "mapping_status",
        ],
    ].copy()

    if scoped_mappings.empty:
        raise CanonicalMappingError(
            "No system mappings found for mapping source: "
            + mapping_source_system
        )

    if scoped_mappings["raw_system_id"].isna().any():
        raise CanonicalMappingError(
            "Mapping source contains null raw_system_id values."
        )

    duplicate_mapping_mask = scoped_mappings.duplicated(
        subset=["raw_system_id"],
        keep=False,
    )
    if duplicate_mapping_mask.any():
        duplicate_ids = sorted(
            scoped_mappings.loc[
                duplicate_mapping_mask,
                "raw_system_id",
            ]
            .astype(str)
            .unique()
            .tolist()
        )
        raise CanonicalMappingError(
            "Mapping source is not many-to-one for raw system identifiers: "
            + ", ".join(duplicate_ids)
        )

    normalized = evidence.merge(
        scoped_mappings,
        how="left",
        on="raw_system_id",
        validate="many_to_one",
        indicator="_mapping_merge",
    )

    if len(normalized) != len(evidence):
        raise CanonicalMappingError(
            "Identity normalization changed the control-evidence row count."
        )

    source_unresolved_mask = normalized["_mapping_merge"].eq("left_only")
    explicit_unmapped_mask = normalized["mapping_status"].eq("UNMAPPED")
    mapped_mask = normalized["mapping_status"].eq("MAPPED")

    invalid_mapped_mask = (
        mapped_mask
        & normalized["canonical_system_id"].isna()
    )
    if invalid_mapped_mask.any():
        affected = sorted(
            normalized.loc[
                invalid_mapped_mask,
                "raw_system_id",
            ]
            .astype(str)
            .unique()
            .tolist()
        )
        raise CanonicalMappingError(
            "Mapped identifiers are missing canonical_system_id: "
            + ", ".join(affected)
        )

    invalid_unmapped_mask = (
        explicit_unmapped_mask
        & normalized["canonical_system_id"].notna()
    )
    if invalid_unmapped_mask.any():
        affected = sorted(
            normalized.loc[
                invalid_unmapped_mask,
                "raw_system_id",
            ]
            .astype(str)
            .unique()
            .tolist()
        )
        raise CanonicalMappingError(
            "UNMAPPED identifiers must not carry canonical_system_id: "
            + ", ".join(affected)
        )

    unknown_status_mask = (
        ~source_unresolved_mask
        & ~normalized["mapping_status"].isin(["MAPPED", "UNMAPPED"])
    )
    if unknown_status_mask.any():
        affected = sorted(
            normalized.loc[
                unknown_status_mask,
                "raw_system_id",
            ]
            .astype(str)
            .unique()
            .tolist()
        )
        raise CanonicalMappingError(
            "Unsupported mapping status for raw identifiers: "
            + ", ".join(affected)
        )

    normalized["identity_status"] = "MAPPED"

    normalized.loc[
        explicit_unmapped_mask | source_unresolved_mask,
        "identity_status",
    ] = "UNMAPPED"

    normalized["identity_reason_code"] = pd.NA

    normalized.loc[
        explicit_unmapped_mask,
        "identity_reason_code",
    ] = "UNRESOLVED_MAPPING"

    normalized.loc[
        source_unresolved_mask,
        "identity_reason_code",
    ] = "MAPPING_REFERENCE_NOT_FOUND"

    normalized["mapping_source_system"] = mapping_source_system

    return normalized.drop(columns=["_mapping_merge"])
