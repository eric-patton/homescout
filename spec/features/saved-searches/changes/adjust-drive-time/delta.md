## MODIFIED

AC-25

Was: saved drive-time areas support preview, persistence and recalculation.

Now: An existing area can change duration without recreation: preserve its reference where present, center, address, matched address, name, reason, direction, provider, public-place declaration and inclusion/exclusion. Save validated new minutes, geometry and generation provenance together through the existing edit operation. Reopening and subsequent runs use that pair; includes remain a union (Work OR Family), exclusions subtract, duplicate source rows stay deduplicated, and other areas and unrelated YAML remain unchanged. Cancel, invalid input and failed routing or save leave the saved pair intact. Decimal minutes remain supported.
