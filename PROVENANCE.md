# Provenance

This repository contains a cleaned headless port of the original BNOT `ibnot` code.

Original reference:

- Fernando de Goes, `bnot: Blue Noise through Optimal Transport` (2012)
- Original legacy tree name: `bnot-src/ibnot`

The current `ibnot_new` version keeps the geometric core and capacity-constrained optimization logic, while removing the legacy Qt/OpenGL GUI path and replacing the SuiteSparse QR dependency with an Eigen-based sparse QR path.

The original license text is preserved in [`COPYING`](COPYING).
