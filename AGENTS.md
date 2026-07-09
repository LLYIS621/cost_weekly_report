# Project Encoding Rules

This project may contain Chinese source text or generated Chinese output.
Preserve the following rules for all work in this directory.

## Encoding

- Keep source files and generated text files in UTF-8.
- Do not convert BOM or line-ending style merely for cleanup. Preserve the
  existing style of a file unless a requested change requires otherwise.
- Python text reads and writes must specify `encoding="utf-8"` or
  `encoding="utf-8-sig"` when intentionally accepting an existing BOM.
- HTML pages must retain `<meta charset="UTF-8">`.

## PowerShell On Windows

- Windows PowerShell 5.1 can read UTF-8 files without a BOM using the wrong
  legacy encoding.
- When reading text with PowerShell, always specify UTF-8 explicitly, for
  example: `Get-Content -LiteralPath 'file.py' -Encoding UTF8`.
- Do not overwrite source files using default-encoding PowerShell commands such
  as bare `Set-Content`, `Out-File`, or `>` / `>>`.
- Prefer patch-based edits for manual source changes.

## Verification

- After editing code or regenerating textual output, run:
  `python check_encoding.py`
- Treat an encoding-check failure as a blocker before delivering changes.
- When checking displayed Chinese content, distinguish terminal rendering
  problems from actual on-disk file corruption by decoding file bytes as UTF-8.

## Dashboard Layout Rules

- KPI cards and report modules should use stable grid tracks, fixed gaps, and
  bounded content groups. Do not rely on leftover space to align important
  metric text.
- For short label/value rows, avoid `justify-content: space-between` inside a
  wide or flexible container. Prefer a fixed two-column grid such as
  `grid-template-columns: 72px auto`, or give the whole information group a
  `max-width`.
- When placing a chart beside metric text, define both the chart column and the
  text group width explicitly enough that chart-to-text spacing stays stable.
  Avoid combining a very small grid gap with an unbounded text column.
- Similar KPI blocks must share a clear type scale: section title, metric label,
  primary number, secondary number, and helper text should each use consistent
  font sizes and weights.
- After adding or changing a KPI/report module, check these visually:
  label/value distance is not excessive, chart/text gap is not cramped, same
  level numbers use the same size, and helper information does not look like a
  separate table unless that is intentional.
