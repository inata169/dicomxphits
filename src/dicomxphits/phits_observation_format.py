"""Bounded parsing of the reviewed fresh PHITS 3.35 xyz/xy dose variant.

These values are provisional presentation data and never execution evidence.
No text in a tally is executed, and no referenced filename is opened here.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import numpy as np

MAX_CELLS = 10_000_000
MAX_TALLY_BYTES = 256 * 1024**2
MAX_HEADER_BYTES = 65536
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?"
SEED = r"[01]{64}"


class ObservationError(ValueError):
    """A sample is unavailable, not a PHITS execution failure."""


def require(condition, reason="unsupported-format"):
    if not condition:
        raise ObservationError(reason)


def checkpoint(deadline):
    require(time.monotonic() <= deadline, "resource-limit")


def number(token):
    require(len(token) <= 64, "resource-limit")
    require(re.fullmatch(NUMBER, token) is not None)
    value = float(token.replace("D", "E").replace("d", "e"))
    require(math.isfinite(value))
    return value


def integer(token):
    require(len(token) <= 16 and re.fullmatch(r"\d+", token) is not None)
    return int(token)


def assignments(text):
    result = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"\s*([\w-]+)\s*=\s*(.*?)\s*(?:#.*)?", line)
        require(match is not None)
        key, value = match.groups()
        require(key not in result)
        result[key] = value.strip()
    return result


@dataclass(frozen=True)
class Mesh:
    title: str
    file: str
    counts: tuple[int, int, int]
    bounds: tuple[tuple[float, float], ...]

    @property
    def cells(self):
        return math.prod(self.counts)


FIXED = {"mesh": "xyz", "axis": "xy", "output": "dose", "part": "all",
         "material": "all", "unit": "0", "epsout": "1",
         "x-type": "2", "y-type": "2", "z-type": "2"}


def mesh_from_fields(fields, *, epsout="1"):
    fixed = dict(FIXED)
    if epsout is None:
        fixed.pop("epsout")
        require("epsout" not in fields)
    else:
        fixed["epsout"] = epsout
    require(all(fields.get(k) == v for k, v in fixed.items()))
    require(isinstance(fields.get("title"), str) and 0 < len(fields["title"]) <= 512)
    require(isinstance(fields.get("file"), str) and 0 < len(fields["file"]) <= 1024)
    counts = tuple(integer(fields.get("n" + axis, "")) for axis in "xyz")
    require(all(n > 0 for n in counts) and math.prod(counts) <= MAX_CELLS, "resource-limit")
    bounds = tuple((number(fields.get(axis + "min", "")), number(fields.get(axis + "max", ""))) for axis in "xyz")
    require(all(lo < hi for lo, hi in bounds))
    return Mesh(fields["title"], fields["file"], counts, bounds)


def prepared_contract(text, expected_file):
    require(len(text.encode("utf-8")) <= 4 * 1024**2, "resource-limit")
    require(re.search(r"(?im)^\s*(?:itall|\$MPI)\b", text) is None)
    # Public segment generation explicitly writes this default. It permits
    # observation setup, not acceptance of an output variance mode: both
    # output records still require independent identity and metadata validation.
    variance_lines = re.findall(r"(?im)^[ \t]*istdev\b[^\r\n]*", text)
    require(len(variance_lines) <= 1 and all(
        re.fullmatch(r"[ \t]*istdev[ \t]*=[ \t]*-1[ \t]*(?:#.*)?", line, re.I)
        for line in variance_lines))
    runtime = {}
    for name in ("maxcas", "maxbch"):
        values = re.findall(r"(?im)^\s*" + name + r"\s*=\s*(\d+)\s*(?:#.*)?$", text)
        require(len(values) == 1)
        runtime[name] = integer(values[0])
        require(runtime[name] > 0)
    omp = re.findall(r"(?im)^\s*\$OMP\s*=\s*(\d+)\s*$", text)
    require(len(omp) == 1 and integer(omp[0]) > 0)
    runtime["threads"] = integer(omp[0])
    found = []
    for block in re.finditer(r"(?ims)^\s*\[\s*T-Deposit\s*\]\s*\r?\n(.*?)(?=^\s*\[|\Z)", text):
        fields = assignments(block[1])
        if fields.get("file") == expected_file:
            found.append(mesh_from_fields(fields))
    require(len(found) == 1)
    return found[0], runtime


def prepared_sumtally_contract(text):
    """Validate the generated PHITS wrapper used for ``isumtally=2``."""

    require(len(text.encode("utf-8")) <= 4 * 1024**2, "resource-limit")
    require(re.search(r"(?im)^\s*(?:itall|\$MPI)\b", text) is None)
    istdev = re.findall(
        r"(?im)^\s*istdev\s*=\s*([+-]?\d+)\s*(?:#.*)?$",
        text,
    )
    require(len(istdev) <= 1 and (not istdev or istdev == ["-1"]))
    runtime = {}
    for name in ("maxcas", "maxbch"):
        values = re.findall(
            r"(?im)^\s*" + name + r"\s*=\s*(\d+)\s*(?:#.*)?$",
            text,
        )
        require(len(values) == 1)
        runtime[name] = integer(values[0])
        require(runtime[name] > 0)
    icntl = re.findall(r"(?im)^\s*icntl\s*=\s*(\d+)\s*(?:#.*)?$", text)
    require(icntl == ["13"])
    omp = re.findall(r"(?im)^\s*\$OMP\s*=\s*(\d+)\s*$", text)
    require(len(omp) == 1 and integer(omp[0]) > 0)
    runtime["threads"] = integer(omp[0])
    found = []
    for block in re.finditer(
        r"(?ims)^\s*\[\s*T-Deposit\s*\]\s*\r?\n(.*?)(?=^\s*\[|\Z)",
        text,
    ):
        field_lines = []
        includes = []
        for line in block[1].splitlines():
            include = re.fullmatch(
                r"\s*infl:\s*\{\s*([^}]+?)\s*\}\s*(?:[#\$!].*)?",
                line,
                re.IGNORECASE,
            )
            if include:
                includes.append(include[1].strip())
            else:
                field_lines.append(line)
        fields = assignments("\n".join(field_lines))
        sumtally_includes = [
            value
            for value in includes
            if value.replace("\\", "/").rsplit("/", 1)[-1].lower()
            == "sumtally.inp"
        ]
        if sumtally_includes:
            require(len(includes) == len(sumtally_includes) == 1)
            found.append(mesh_from_fields(fields, epsout="0"))
    require(len(found) == 1)
    return found[0], runtime


def _sumtally_output_fields(header, expected_file):
    lines = header.splitlines()
    require(lines and re.fullmatch(r"\s*\[\s*T-Deposit\s*\]\s*", lines[0]))
    starts = [
        index
        for index, line in enumerate(lines)
        if line.strip().lower() == "sumtally start"
    ]
    ends = [
        index
        for index, line in enumerate(lines)
        if line.strip().lower() == "sumtally end"
    ]
    require(len(starts) == len(ends) == 1 and 0 < starts[0] < ends[0])
    start, end = starts[0], ends[0]
    fields = assignments("\n".join(lines[1:start] + lines[end + 1 :]))

    values = {}
    source_lines = []
    for line in lines[start + 1 : end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.fullmatch(r"\s*([\w-]+)\s*=\s*(.*?)\s*(?:#.*)?", line)
        if match:
            key, value = match.groups()
            require(key not in values)
            values[key] = value.strip()
        else:
            source_lines.append(stripped)
    require(set(values) == {"isumtally", "nfile", "sfile", "sumfactor"})
    require(values["isumtally"] == "2")
    nfile = integer(values["nfile"])
    require(0 < nfile <= 10_000, "resource-limit")
    sumfactor = number(values["sumfactor"])
    require(sumfactor > 0)
    require(
        values["sfile"].replace("\\", "/").rsplit("/", 1)[-1]
        == expected_file
    )

    sources = []
    cursor = 0
    for _index in range(nfile):
        require(cursor < len(source_lines))
        candidate = source_lines[cursor]
        cursor += 1
        combined = re.fullmatch(r"(.+?)\s+(" + NUMBER + r")", candidate)
        if combined:
            source_path, weight_token = combined.groups()
        else:
            source_path = candidate
            require(cursor < len(source_lines))
            weight_token = source_lines[cursor]
            cursor += 1
            require(re.fullmatch(NUMBER, weight_token) is not None)
        require(0 < len(source_path) <= 4096 and "\x00" not in source_path)
        weight = number(weight_token)
        require(weight > 0)
        sources.append({"path": source_path, "weight": weight})
    require(cursor == len(source_lines))
    metadata = {
        "isumtally": 2,
        "nfile": nfile,
        "sources": sources,
        "sfile": values["sfile"],
        "sumfactor": sumfactor,
    }
    return fields, metadata


def parse_batch(raw, prepared):
    require(len(raw) <= MAX_HEADER_BYTES, "resource-limit")
    text = raw.decode("ascii").replace("\r\n", "\n")
    initial = re.fullmatch(r"(\d+) <--- remaining batch number\n\n-{79}\n start calculation\n-{79}\n\n date = \d{4}-\d{2}-\d{2}\n time = \d{2}h \d{2}m \d{2}\n\n", text)
    if initial:
        remaining = integer(initial[1])
        require(remaining == prepared)
        return remaining
    # Full updated record, not merely a first-line integer.
    pattern = (r"(\d+) <--- number of remaining batches \n\n-{79}\n"
        r"bat\[\s*(\d+)\] ncas =\s*(\d+)\.\n"
        r" bitrseed = " + SEED + r"\n\s*cpu time =\s*(" + NUMBER + r") s\.\n\n"
        r" date = \d{4}-\d{2}-\d{2}\n time = \d{2}h \d{2}m \d{2}s\n\n"
        r"-{79}\nnext initial random seed:\n bitrseed = " + SEED + r"\n")
    match = re.fullmatch(pattern, text)
    require(match is not None)
    remaining, batch, histories = (integer(match[i]) for i in (1, 2, 3))
    require(0 <= remaining <= prepared and 1 <= batch <= prepared and histories > 0)
    require(number(match[4]) >= 0)
    return remaining


LIVE_PARSER = "phits-3.35-windows-openmp-xyz-xy-variance-v2"
LIVE_PARSERS = frozenset({LIVE_PARSER, "phits-3.35-windows-openmp-xyz-xy-history-v1"})


def parse_identity(header, stdout, threads):
    require(len(header) <= MAX_HEADER_BYTES and len(stdout) <= MAX_HEADER_BYTES, "resource-limit")
    text = header.decode("ascii")
    versions = re.findall(r"Version\s*=\s*(\S+)", text)
    require(versions == ["3.350"], "unsupported-identity")
    workers = re.findall(rb"OpenMP PARALLEL PROCESS\s+(\d+)/\s*(\d+)\s+@ IP\(MPI\)=\s*(\d+)", stdout)
    require(bool(workers), "waiting-identity")
    seen = set()
    for ordinal, total, mpi in workers:
        ordinal, total, mpi = int(ordinal), int(total), int(mpi)
        require(total == threads and mpi == 0 and 1 <= ordinal <= total, "unsupported-identity")
        require(ordinal not in seen, "unsupported-identity")
        seen.add(ordinal)
    require(len(seen) == threads, "waiting-identity")
    return LIVE_PARSER


def parse_tally(raw, expected, role, deadline, *, sumtally=False, live_maxbch=None):
    require(role in {"dose", "error"})
    require(len(raw) <= MAX_TALLY_BYTES, "resource-limit")
    checkpoint(deadline)
    text = raw.decode("ascii").replace("\r\n", "\n")
    first = text.find("#newpage:\n")
    require(0 < first <= MAX_HEADER_BYTES)
    header = text[:first]
    require(header.startswith("[ T-Deposit ]\n"))
    if sumtally:
        fields, metadata = _sumtally_output_fields(header, expected.file)
        allowed = (set(FIXED) - {"epsout"}) | {
            "title", "file", "nx", "ny", "nz", "xmin", "xmax", "ymin",
            "ymax", "zmin", "zmax", "letmat", "dedxfnc", "deposit",
            "2D-type", "mother",
        }
        parsed_mesh = mesh_from_fields(fields, epsout=None)
    else:
        fields = assignments(header.split("\n", 1)[1])
        allowed = set(FIXED) | {"title", "file", "nx", "ny", "nz", "xmin", "xmax", "ymin", "ymax", "zmin", "zmax",
                               "letmat", "dedxfnc", "deposit", "2D-type", "mother"}
        parsed_mesh = mesh_from_fields(fields)
    require(set(fields) == allowed)
    require(fields["letmat"] == fields["dedxfnc"] == fields["deposit"] == "0")
    require(fields["2D-type"] == "3" and fields["mother"] == "all")
    require(parsed_mesh == expected, "mesh-mismatch")
    restart_marker = "# Information for Restart Calculation\n"
    if sumtally:
        require(restart_marker not in text, "unsupported-restart")
        body = text[first + len("#newpage:\n"):]
    else:
        require(text.count(restart_marker) == 1)
        body, restart = text[first + len("#newpage:\n"):].split(restart_marker)
        require(restart.startswith("# This calculation was newly started\n"), "unsupported-restart")
        lines = restart.splitlines()
        require(len(lines) == 6 and restart.endswith("\n"))
        metadata = {}
        comments = {"istdev": "1:Batch variance, 2:History variance",
                    "resc2": "Total source weight or Total source weight / maxcas",
                    "resc3": "Total history number or Total batch number",
                    "maxcas": "History / Batch, only used for istdev=1",
                    "bitrseed": "bit data of rseed"}
        for line, name in zip(lines[1:6], comments):
            match = re.fullmatch(r"# " + name + r"\s*=\s*(\S+) # " + re.escape(comments[name]), line)
            require(match is not None)
            token = match[1]
            if name == "bitrseed":
                require(re.fullmatch(SEED, token) is not None)
                metadata[name] = token
            else:
                value = number(token)
                require(value > 0)
                if live_maxbch is not None:
                    # Preserve exact source weights and integer metadata for pairing.
                    exact = Decimal(token.replace("D", "E").replace("d", "e"))
                    if name == "resc2":
                        value = exact
                    else:
                        require(exact == exact.to_integral_value())
                        value = int(exact)
                metadata[name] = value
        require(metadata["istdev"] == 2 or (live_maxbch is not None and metadata["istdev"] == 1),
                "unsupported-variance")
        if metadata["istdev"] == 1:
            require(metadata["resc3"] <= live_maxbch, "batch-budget")
        require(all(value == int(value) for value in (metadata["resc3"], metadata["maxcas"])))
    pages = body.split(" newpage:\n")
    require(len(pages) == expected.counts[2])
    output = np.empty(expected.cells, dtype=np.float64)
    nx, ny, nz = expected.counts
    data_marker = "# ( ( data(x,y), x = 1, nx ), y = ny, 1, -1 )\n"
    role_label = "Dose [Gy/source]" if role == "dose" else "Relative Error"
    for index, page in enumerate(pages, 1):
        checkpoint(deadline)
        page_header = re.match(r"#   no\. =\s*(\d+)   iz  =\s*(\d+)   part\. = all\s*\n#   z = \(\s*(" + NUMBER + r")\s+-\s+(" + NUMBER + r")\s+\)\n", page)
        require(page_header is not None and integer(page_header[1]) == index and integer(page_header[2]) == index)
        lo, hi = expected.bounds[2]
        step = (hi - lo) / nz
        # Compare to the actual printed precision, not a physical tolerance.
        require(number(page_header[3]) == float(f"{lo + (index-1)*step:.4e}") and
                number(page_header[4]) == float(f"{lo + index*step:.4e}"), "slice-mismatch")
        require(page.count("msdl: {\\it calculated by \\PHITS  3.35}") == 1, "unsupported-identity")
        page_identity = re.findall(
            r"(?m)^'no\. =[ \t]*(0|[1-9]\d*),[ \t]+iz =[ \t]*(0|[1-9]\d*)'[ \t]*$",
            page,
        )
        require(page_identity == [(str(index), str(index))])
        count_match = re.findall(r"#  ny =\s*(\d+)   nx =\s*(\d+)", page)
        require(count_match == [(str(ny), str(nx))])
        require(page.count(data_marker) == 1)
        pre, data_tail = page.split(data_marker)
        require(pre.count("hc:") == 0)
        hc = re.match(r"\nhc:  y =\s*(" + NUMBER + r")\s+to\s*(" + NUMBER + r")\s+by\s*(" + NUMBER +
            r")\s+; x =\s*(" + NUMBER + r")\s+to\s*(" + NUMBER + r")\s+by\s*(" + NUMBER + r")\s+;\n", data_tail)
        require(hc is not None)
        coordinates = [number(hc[j]) for j in range(1, 7)]
        (xl, xh), (yl, yh), _ = expected.bounds
        dx, dy = (xh-xl)/nx, (yh-yl)/ny
        require(all(a == float(f"{b:.7g}") for a, b in zip(coordinates,
            (yh-dy/2, yl+dy/2, dy, xl+dx/2, xh-dx/2, dx))), "coordinate-mismatch")
        tail = data_tail[hc.end():]
        split = tail.find("#" + "-" * 78)
        require(split >= 0)
        numeric, plot = tail[:split], tail[split:]
        consumed = 0
        for match in re.finditer(r"\S+", numeric):
            if consumed % 4096 == 0:
                checkpoint(deadline)
            require(consumed < nx*ny)
            value = number(match[0])
            require(value >= 0, "invalid-numeric")
            output[(index-1)*nx*ny + consumed] = value
            consumed += 1
        require(consumed == nx*ny)
        require(plot.count("hc:") == 1 and len(re.findall(r"(?m)^y: " + re.escape(role_label) + r" *$", plot)) == 1, "role-mismatch")
        legend = plot.split("hc:", 1)[1].split("\n", 1)[1].split("z:", 1)[0]
        require(legend.split() == [str(i) for i in range(1, 101)])
        require("\ne:\n" in plot and "z: xorg[-1.03/0.05]" in plot)
        # Every remaining line is an inert supported plotting/comment command.
        for line in (pre + plot).splitlines():
            require(len(line) <= 8192, "resource-limit")
            require(not line.strip() or line == "hc: y= 0.005 to 0.995 by 0.01 ; x= 0.5 to 0.5 by 1 ;" or
                    re.match(r"^(?:#|'no\. =|msu[cd]:|msd[rl]:|[xypz]:|set:|wt:|e:|\\vspace|  (?:zmin|zmax|part\.)|\s*\d+(?:\s+\d+)*\s*$)", line))
        require(plot.rstrip().endswith("#" + "-" * 78) or
                re.search(r"p: ymin\([^\n]+\) ymax\([^\n]+\)\s*\n\s*\Z", plot) is not None)
    checkpoint(deadline)
    return output, metadata


def isocenter_flat_index(mesh):
    """Locate the unique xyz cell whose open interior contains isocenter."""
    indices = []
    zero = Decimal(0)
    for (raw_lo, raw_hi), count in zip(mesh.bounds, mesh.counts):
        lo, hi = Decimal(str(raw_lo)), Decimal(str(raw_hi))
        require(lo < zero < hi, "isocenter-unavailable")
        step = (hi - lo) / Decimal(count)
        scaled = (zero - lo) / step
        # An isocenter on a bin boundary belongs to neither open interior.
        require(scaled != scaled.to_integral_value(), "isocenter-unavailable")
        index = int(scaled)
        require(0 <= index < count, "isocenter-unavailable")
        require(lo + step * index < zero < lo + step * (index + 1),
                "isocenter-unavailable")
        indices.append(index)
    x, y, z = indices
    nx, ny, _nz = mesh.counts
    # PHITS xyz/xy pages list x ascending and y descending for each z page.
    return (z * mesh.counts[1] + (mesh.counts[1] - 1 - y)) * nx + x


def paired_isocenter_error(dose_raw, error_raw, mesh, maxcas, deadline, *, live_maxbch=None):
    dose, error, _metadata = paired_tally_values(
        dose_raw,
        error_raw,
        mesh,
        maxcas,
        deadline,
        live_maxbch=live_maxbch,
    )
    index = isocenter_flat_index(mesh)
    require(dose[index] > 0 and error[index] > 0, "isocenter-unavailable")
    result = {"relative_error_percent": float(error[index]) * 100}
    require(all(math.isfinite(v) for v in result.values()), "invalid-numeric")
    checkpoint(deadline)
    return result


def paired_tally_values(dose_raw, error_raw, mesh, maxcas, deadline, *, live_maxbch=None):
    """Return one completely validated PHITS 3.35 dose/error grid pair."""

    dose, dose_metadata = parse_tally(dose_raw, mesh, "dose", deadline, live_maxbch=live_maxbch)
    error, error_metadata = parse_tally(error_raw, mesh, "error", deadline, live_maxbch=live_maxbch)
    require(
        dose_metadata == error_metadata
        and dose_metadata["maxcas"] == maxcas,
        "pair-mismatch",
    )
    checkpoint(deadline)
    return dose, error, dose_metadata


def paired_sumtally_values(dose_raw, error_raw, mesh, deadline):
    """Return one validated PHITS 3.35 ``isumtally=2`` dose/error pair."""

    dose, dose_metadata = parse_tally(
        dose_raw,
        mesh,
        "dose",
        deadline,
        sumtally=True,
    )
    error, error_metadata = parse_tally(
        error_raw,
        mesh,
        "error",
        deadline,
        sumtally=True,
    )
    require(dose_metadata == error_metadata, "pair-mismatch")
    checkpoint(deadline)
    return dose, error, dose_metadata
