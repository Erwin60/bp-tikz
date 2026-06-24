# Contributing

Thanks for your interest in improving `generate_bp_tikz.py`.

## Reporting issues

Please open a GitHub issue and include:

- the exact command line you ran,
- a minimal (anonymized) example CSV that triggers the problem,
- the observed behavior and what you expected,
- your environment (OS, Python version, TeX distribution; on iOS, a-Shell
  and/or Texifier version).

Do **not** attach real, identifiable health data. Use synthetic or anonymized
values like those in `examples/bp_anon_example.csv`.

## Pull requests

- Keep the tool dependency-free (Python standard library only).
- Preserve deterministic output: the same input, date window, and parameters
  must produce identical output.
- If you add a command-line parameter, document it in the `--help` text, in
  both Markdown manuals (`docs/`), and in the parameter table of the IEEE
  papers.
- Verify that the generated LaTeX still compiles with `tikz` + `pgfplots`
  (`compat=1.18`) and that the one-page standalone still fills the page height.
- Include a short note in `CHANGELOG.md`.

## Scope

This project is a focused HBPM visualization tool. It intentionally does not
attempt diagnostic interpretation. Please keep clinical thresholds presented as
comparison/orientation lines, never as individual target values.

## Tested environments

Changes are tested on macOS (desktop Python + TeX Live/MacTeX) and on
iPad/iPhone via a-Shell (local Python + TeX Live) with Texifier for editing and
typesetting. Contributions that keep these environments working are appreciated;
support for additional platforms is welcome but should be clearly marked as
untested if you cannot verify it.
