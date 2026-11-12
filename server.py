"""
SPSS MCP server.

Connects an MCP client to IBM SPSS Statistics on this Windows machine.

Two layers:
  1. Data layer (pyreadstat) - read .sav files, variables, labels, values.
     100% reliable, pure Python, needs no SPSS license.
  2. Engine layer (stats.exe batch) - run real SPSS syntax and return its output.

Note: this server does NOT attach to an already-open SPSS GUI window. Save your
data to a .sav file, then point the tools at that file.
"""
import os
import glob
import json
import tempfile
import subprocess

import pyreadstat
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("spss")


# ---------------------------------------------------------------------------
# Locating SPSS
# ---------------------------------------------------------------------------
def find_stats_exe():
    """Return the path to stats.exe, or None if not found."""
    env = os.environ.get("SPSS_STATS_EXE")
    if env and os.path.isfile(env):
        return env
    patterns = [
        r"C:\Program Files\IBM\SPSS\Statistics\*\stats.exe",
        r"C:\Program Files\IBM\SPSS Statistics\*\stats.exe",
        r"C:\Program Files (x86)\IBM\SPSS\Statistics\*\stats.exe",
    ]
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]  # highest version
    return None


STATS_EXE = find_stats_exe()

# Batch argument template. Different SPSS installs accept slightly different
# flags; override with SPSS_BATCH_ARGS if the default does not work.
# Placeholders: {exe} {syntax} {out} {err}
DEFAULT_BATCH_ARGS = os.environ.get(
    "SPSS_BATCH_ARGS",
    '"{exe}" "{syntax}" -production -out "{out}" -type text',
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def spss_info() -> str:
    """Show the detected SPSS installation and whether the server is ready."""
    return json.dumps(
        {
            "stats_exe": STATS_EXE,
            "ready_for_syntax": STATS_EXE is not None,
            "data_layer": "pyreadstat (always available)",
            "batch_args_template": DEFAULT_BATCH_ARGS,
            "note": "Does not attach to the open SPSS GUI. Work on .sav files.",
        },
        indent=2,
    )


@mcp.tool()
def read_sav(path: str, max_rows: int = 20) -> str:
    """
    Read a .sav file: variable names, N, a sample of rows, and variable labels.

    path: absolute path to the .sav file.
    max_rows: how many data rows to include in the preview.
    """
    if not os.path.isfile(path):
        return f"File tidak ditemukan: {path}"
    df, meta = pyreadstat.read_sav(path)
    preview = df.head(max_rows)
    out = {
        "file": path,
        "n_rows": int(df.shape[0]),
        "n_columns": int(df.shape[1]),
        "columns": list(df.columns),
        "variable_labels": meta.column_names_to_labels,
        "preview": json.loads(preview.to_json(orient="records", force_ascii=False)),
    }
    return json.dumps(out, indent=2, ensure_ascii=False)


@mcp.tool()
def describe_sav(path: str) -> str:
    """
    Full metadata of a .sav file: each variable's type, measure level,
    value labels, and missing-value definitions. Read this before analysing.
    """
    if not os.path.isfile(path):
        return f"File tidak ditemukan: {path}"
    _, meta = pyreadstat.read_sav(path, metadataonly=True)
    out = {
        "file": path,
        "n_rows": meta.number_rows,
        "variables": [],
    }
    for name in meta.column_names:
        out["variables"].append(
            {
                "name": name,
                "label": meta.column_names_to_labels.get(name),
                "type": meta.readstat_variable_types.get(name),
                "measure": meta.variable_measure.get(name),
                "value_labels": meta.variable_value_labels.get(name, {}),
                "missing_ranges": meta.missing_ranges.get(name, []),
            }
        )
    return json.dumps(out, indent=2, ensure_ascii=False)


@mcp.tool()
def export_csv(sav_path: str, csv_path: str) -> str:
    """Convert a .sav file to CSV (UTF-8). Returns the output path and row count."""
    if not os.path.isfile(sav_path):
        return f"File tidak ditemukan: {sav_path}"
    df, _ = pyreadstat.read_sav(sav_path)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return json.dumps({"written": csv_path, "rows": int(df.shape[0])}, indent=2)


@mcp.tool()
def run_syntax(syntax: str, data_file: str = "") -> str:
    """
    Run SPSS command syntax through the batch engine and return the output.

    syntax: SPSS syntax (e.g. "FREQUENCIES VARIABLES=gender.").
    data_file: optional .sav path; if given, a GET FILE line is prepended so
               the syntax runs against that dataset.

    Requires stats.exe (check with spss_info). If the batch flags are rejected,
    adjust the SPSS_BATCH_ARGS environment variable (see README).
    """
    if STATS_EXE is None:
        return "stats.exe tidak ketemu. Set env SPSS_STATS_EXE ke path stats.exe."

    workdir = tempfile.mkdtemp(prefix="spssmcp_")
    syntax_path = os.path.join(workdir, "job.sps")
    out_path = os.path.join(workdir, "out.txt")
    err_path = os.path.join(workdir, "err.txt")

    body = ""
    if data_file:
        if not os.path.isfile(data_file):
            return f"data_file tidak ditemukan: {data_file}"
        body += f'GET FILE="{data_file}".\n'
    body += syntax.rstrip()
    if not body.rstrip().endswith("."):
        body += "."
    body += "\n"

    with open(syntax_path, "w", encoding="utf-8") as f:
        f.write(body)

    cmd_str = DEFAULT_BATCH_ARGS.format(
        exe=STATS_EXE, syntax=syntax_path, out=out_path, err=err_path
    )
    try:
        proc = subprocess.run(
            cmd_str, shell=True, capture_output=True, text=True, timeout=600
        )
    except subprocess.TimeoutExpired:
        return "SPSS batch timeout (600s)."

    result = {"exit_code": proc.returncode, "syntax_file": syntax_path}
    for key, p in (("output", out_path), ("errors", err_path)):
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                result[key] = f.read()
    if "output" not in result:
        result["output"] = proc.stdout or ""
        result["stderr"] = proc.stderr or ""
        result["hint"] = (
            "Tidak ada file output. Flag batch mungkin salah untuk SPSS versi ini. "
            "Sesuaikan env SPSS_BATCH_ARGS (lihat README)."
        )
    return json.dumps(result, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
