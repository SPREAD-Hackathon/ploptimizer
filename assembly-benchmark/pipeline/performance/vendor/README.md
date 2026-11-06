# Wick/Holt assessment source

`wick_assess_assembly.py` is an unmodified copy of `scripts/assess_assembly.py`
from Ryan R. Wick and Kathryn E. Holt's Long-read-assembler-comparison repository,
revision `4bc676c4a5b01602abf1143bfefcaab4cc0dde97`.

Source: https://github.com/rrwick/Long-read-assembler-comparison
Study: https://doi.org/10.12688/f1000research.21782.4
Licence: https://creativecommons.org/licenses/by/4.0/
Attribution: Ryan R. Wick and Kathryn E. Holt.

The adapter checks mapper return codes and source hashes, retains mapping
evidence, and represents unmeasured identity/indel values as null instead of
the upstream numeric-zero placeholder. Selection and metric calculations use
the pinned upstream primitives. Original study scores are not imported as ours.
