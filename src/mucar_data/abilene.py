from dataclasses import dataclass
from statistics import median
import csv
import gzip
import hashlib
import io
import math
import re
import tarfile
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class Demand:
    src: str
    dst: str
    value: float


@dataclass(frozen=True)
class NativeMatrix:
    timestamp: str
    nodes: Tuple[str, ...]
    demands: Tuple[Demand, ...]
    source_name: str


def _section(text: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*\(", text)
    if not match:
        raise ValueError(f"missing {name} section")
    start = match.end()
    depth = 1
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return text[start:index]
    raise ValueError(f"unterminated {name} section")


def parse_native_matrix(text: str, source_name: str = "<memory>") -> NativeMatrix:
    node_section = _section(text, "NODES")
    demand_section = _section(text, "DEMANDS")
    nodes = tuple(
        match.group(1)
        for line in node_section.splitlines()
        if (match := re.match(r"\s*([^\s()]+)\s*\(", line))
    )
    if not nodes:
        raise ValueError(f"{source_name}: no nodes")

    demands = []
    for line in demand_section.splitlines():
        fields = line.strip().split()
        if not fields or fields[0].startswith("#"):
            continue
        native_match = re.match(
            r"\s*\S+\s+\(\s*(\S+)\s+(\S+)\s*\)\s+\S+\s+(\S+)", line
        )
        if native_match:
            src, dst, raw_value = native_match.groups()
        elif len(fields) >= 4:
            src, dst, raw_value = fields[1], fields[2], fields[3]
        else:
            raise ValueError(f"{source_name}: malformed demand line: {line!r}")
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise ValueError(f"{source_name}: invalid demand value {raw_value!r}") from exc
        if src == dst or src not in nodes or dst not in nodes:
            raise ValueError(f"{source_name}: invalid OD pair {src}->{dst}")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{source_name}: demand must be finite and nonnegative")
        demands.append(Demand(src, dst, value))

    timestamp_match = re.search(r"\bTIMESTAMP\s+([^\s)]+)", text, re.IGNORECASE)
    if not timestamp_match:
        timestamp_match = re.search(r"^\s*time\s*=\s*([^\s)]+)", text, re.MULTILINE | re.IGNORECASE)
    if not timestamp_match:
        raise ValueError(f"{source_name}: missing timestamp")
    return NativeMatrix(timestamp_match.group(1), nodes, tuple(demands), source_name)


def dense_demands(matrix: NativeMatrix):
    values = {(demand.src, demand.dst): demand.value for demand in matrix.demands}
    return {
        (src, dst): values.get((src, dst), 0.0)
        for src in matrix.nodes
        for dst in matrix.nodes
        if src != dst
    }


def iter_native_archive(path: Path):
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError(f"unsafe archive member: {member.name}")
            if not member.isfile():
                continue
            stream = archive.extractfile(member)
            if stream is None:
                continue
            text = stream.read().decode("utf-8", "strict")
            yield parse_native_matrix(text, member.name)


def extract_native_archive(path: Path, destination: Path):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    extracted = []
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError(f"unsafe archive member: {member.name}")
            if not member.isfile():
                continue
            stream = archive.extractfile(member)
            if stream is None:
                continue
            target = destination / name.name
            with target.open("wb") as output:
                output.write(stream.read())
            extracted.append(target)
    return extracted


def timestamp_audit(timestamps):
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("timestamps must be unique")
    ordered = sorted(timestamps)
    return {
        "unique_count": len(timestamps),
        "archive_order_inversions": sum(
            current <= previous for previous, current in zip(timestamps, timestamps[1:])
        ),
        "first_timestamp": ordered[0] if ordered else None,
        "last_timestamp": ordered[-1] if ordered else None,
    }


def process_matrix_files(paths, output_path: Path, train_count: int):
    index = []
    canonical_nodes = None
    for path in paths:
        path = Path(path)
        matrix = parse_native_matrix(path.read_text(encoding="utf-8"), str(path))
        if canonical_nodes is None:
            canonical_nodes = matrix.nodes
        elif matrix.nodes != canonical_nodes:
            raise ValueError(f"node order changed in {path}")
        dense = dense_demands(matrix)
        index.append((matrix.timestamp, path, sum(dense.values())))
    index.sort(key=lambda item: item[0])
    timestamp_audit([item[0] for item in index])
    if not 0 < train_count <= len(index):
        raise ValueError("invalid train_count")
    scale = float(median(item[2] for item in index[:train_count]))
    if scale <= 0:
        raise ValueError("training total median must be positive")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                writer = csv.writer(text, lineterminator="\n")
                writer.writerow([
                    "timestamp_index", "timestamp", "src_id", "dst_id", "demand_raw",
                    "total_demand", "global_intensity", "od_share",
                ])
                for timestamp_index, (timestamp, path, total) in enumerate(index):
                    matrix = parse_native_matrix(path.read_text(encoding="utf-8"), str(path))
                    dense = dense_demands(matrix)
                    for (src, dst), value in dense.items():
                        writer.writerow([
                            timestamp_index, timestamp, src, dst, format(value, ".12g"),
                            format(total, ".12g"), format(total / scale if total else 0.0, ".12g"),
                            format(value / total if total else 0.0, ".12g"),
                        ])
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return {
        "matrix_count": len(index),
        "node_count": len(canonical_nodes or ()),
        "directed_od_count": len(canonical_nodes or ()) * (len(canonical_nodes or ()) - 1),
        "first_timestamp": index[0][0],
        "last_timestamp": index[-1][0],
        "training_total_median": scale,
        "sha256": digest,
        "byte_size": output_path.stat().st_size,
    }


def normalize_records(records: Sequence[Sequence[Tuple[str, str, float]]], train_count: int):
    if not 0 < train_count <= len(records):
        raise ValueError("train_count must select a nonempty prefix")
    totals = [sum(value for _, _, value in slot) for slot in records]
    scale = float(median(totals[:train_count]))
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("training total median must be positive")

    output = []
    zero_total_slots = 0
    for index, (slot, total) in enumerate(zip(records, totals)):
        if total == 0:
            zero_total_slots += 1
        output.append([
            {
                "timestamp_index": index,
                "src_id": src,
                "dst_id": dst,
                "demand_raw": value,
                "total_demand": total,
                "global_intensity": total / scale if total else 0.0,
                "od_share": value / total if total else 0.0,
            }
            for src, dst, value in slot
        ])
    return output, {
        "training_total_median": scale,
        "zero_total_slots": zero_total_slots,
        "train_count": train_count,
    }
