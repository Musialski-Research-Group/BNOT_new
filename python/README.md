# Python Wrapper

This project provides a thin Python wrapper around the `ibnot_new_cli`
executable. It does not expose CGAL or bind the C++ core in-process.

The wrapper can:

- write grayscale `.pgm` inputs
- invoke the CLI as a subprocess
- parse the emitted `.txt` stats
- optionally convert `.eps` outputs to `.png` using Ghostscript

Typical usage assumes the main repo checkout is present and the CLI is available
either from:

- `ibnot_cli/prebuilt/linux-x86_64/ibnot_new_cli`
- `ibnot_cli/build/ibnot_new_cli`

or via an explicit `IBNOT_CLI_BIN` environment variable.

Install it into the same environment you use for the CLI:

```bash
python -m pip install -e "python[notebook]"
```

Then import `ibnot_cli_wrapper` and call the subprocess helpers.

Notebook workflow:

- local notebook: `python/notebooks/bnot_quickstart.ipynb`
- Colab notebook: `python/notebooks/bnot_quickstart_colab.ipynb`
- local generated outputs: `python/notebooks/_generated/`
- Colab-generated outputs inside the cloned repo: `python/notebooks/_generated_colab/`

The notebook uses the shipped CLI through the wrapper and demonstrates three
`512x512` fields at `1024` points:

- uniform
- left-to-right linear ramp
- normalized 2D sine landscape

The wrapper now exposes the main rendering controls used by the notebooks:

- mask size, via the generator helpers such as `make_uniform(size=...)`
- output render size, via `render_width=` and `render_height=`
- rendered point size, via `point_radius=`
- PNG rasterization density, via `dpi=`

The Colab notebook also supports uploading an arbitrary image, converting it to
grayscale with Pillow, resizing it to the configured mask size, and running the
same CLI pipeline on that uploaded map.
