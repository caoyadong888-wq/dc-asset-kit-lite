#!/usr/bin/env python3
"""Parse switch and server inventory dumps into normalized serial records.

Auto-detects three formats:

* Cisco-style ``show inventory`` (NAME / DESCR / PID / VID / SN)
* ``ipmitool fru print``
* ``lshw -json``
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DumpRecord:
    sn: str
    pn: str
    host: str
    port: str
    source: str
    fmt: str = ""
    name: str = ""


_PLACEHOLDER_SN = {
    "",
    "N/A",
    "NA",
    "NONE",
    "NULL",
    "UNKNOWN",
    "NOT SPECIFIED",
    "NOT AVAILABLE",
    "TO BE FILLED BY O.E.M.",
    "XXXXXXXXXX",
}

# Interface names only. Chassis, supervisor, and FRU device labels stay blank
# so they are not compared as if they were front-panel ports.
_IFACE_RE = re.compile(
    r"(?<![A-Za-z])("
    r"(?:Ethernet|GigabitEthernet|HundredGigE|TenGigabitEthernet|Eth|Gi|Te)"
    r"\d+(?:/\d+){1,3}"
    r"|NIC\d+"
    r")",
    re.IGNORECASE,
)

# SN stays on the PID line. A blank SN must not swallow the next NAME token.
_CISCO_BLOCK = re.compile(
    r'NAME:\s*"(?P<name>[^"]*)"\s*,\s*DESCR:\s*"(?P<descr>[^"]*)"\s*'
    r"PID:\s*(?P<pid>.*?)\s*,\s*VID:\s*(?P<vid>.*?)\s*,\s*SN:[ \t]*(?P<sn>.*?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_PROMPT_RE = re.compile(r"(?m)^([A-Za-z0-9][A-Za-z0-9._-]*)\s*[>#]")
_HOST_COMMENT_RE = re.compile(r"(?mi)^[ \t]*#[ \t]*host:[ \t]*(\S+)")


def norm_sn(value: str | None) -> str:
    """Strip ends and uppercase. Internal spaces stay."""
    return (value or "").strip().upper()


def norm_pn(value: str | None) -> str:
    text = (value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text.upper()


def norm_host(value: str | None) -> str:
    return (value or "").strip()


def canonicalize_port(value: str | None) -> str:
    match = _IFACE_RE.search(value or "")
    if not match:
        return ""
    token = match.group(1)
    lower = token.lower()
    if lower.startswith("ethernet"):
        return "Ethernet" + token[len("ethernet") :]
    if lower.startswith("nic"):
        return "NIC" + token[3:]
    return token


def is_placeholder_sn(sn: str) -> bool:
    cleaned = norm_sn(sn)
    if cleaned in _PLACEHOLDER_SN:
        return True
    compact = cleaned.replace(" ", "")
    if compact and set(compact) <= {"0"}:
        return True
    return False


def detect_format(text: str, hint: str = "") -> str:
    sample = text.lstrip("\ufeff").lstrip()
    name = (hint or "").lower()
    if sample.startswith("{") or sample.startswith("["):
        return "lshw_json"
    if "FRU Device Description" in text:
        return "ipmitool_fru"
    if re.search(r'NAME:\s*"', text) and re.search(r"\bSN:\s*", text, re.IGNORECASE):
        return "cisco_inventory"
    if "ipmitool" in name or name.endswith("fru.txt"):
        return "ipmitool_fru"
    if name.endswith(".json"):
        return "lshw_json"
    raise ValueError(f"unknown dump format: {hint or 'stdin'}")


def parse_text(text: str, source: str = "", hint: str = "") -> list[DumpRecord]:
    kind = detect_format(text, hint or source)
    if kind == "cisco_inventory":
        return _parse_cisco(text, source)
    if kind == "ipmitool_fru":
        return _parse_fru(text, source)
    if kind == "lshw_json":
        return _parse_lshw(text, source)
    raise ValueError(f"unknown dump format: {kind}")


def parse_dump(path: str | Path) -> list[DumpRecord]:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8-sig")
    return parse_text(text, source=str(file_path), hint=file_path.name)


def _file_host(text: str) -> str:
    comment = _HOST_COMMENT_RE.search(text)
    if comment:
        return norm_host(comment.group(1))
    prompts = _PROMPT_RE.findall(text)
    if prompts:
        return norm_host(prompts[0])
    return ""


def _parse_cisco(text: str, source: str) -> list[DumpRecord]:
    host = _file_host(text)
    records: list[DumpRecord] = []
    for match in _CISCO_BLOCK.finditer(text):
        raw_sn = match.group("sn")
        if is_placeholder_sn(raw_sn):
            continue
        name = match.group("name").strip()
        descr = match.group("descr").strip()
        port = canonicalize_port(name) or canonicalize_port(descr)
        records.append(
            DumpRecord(
                sn=norm_sn(raw_sn),
                pn=norm_pn(match.group("pid")),
                host=host,
                port=port,
                source=source,
                fmt="cisco_inventory",
                name=name,
            )
        )
    return records


def _parse_fru(text: str, source: str) -> list[DumpRecord]:
    host = _file_host(text)
    blocks = re.split(r"(?m)^(?=FRU Device Description\s*:)", text)
    records: list[DumpRecord] = []
    pairs = (
        ("chassis serial", "chassis part number", "chassis"),
        ("board serial", "board part number", "board"),
        ("product serial", "product part number", "product"),
    )
    for block in blocks:
        if "FRU Device Description" not in block:
            continue
        header = re.search(r"FRU Device Description\s*:\s*(.+)", block)
        device = header.group(1).strip() if header else ""
        port = canonicalize_port(device)
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip().lower()] = value.strip()
        for serial_key, part_key, label in pairs:
            raw_sn = fields.get(serial_key, "")
            if is_placeholder_sn(raw_sn):
                continue
            pn = fields.get(part_key, "")
            if not pn and label == "product":
                pn = fields.get("product name", "")
            records.append(
                DumpRecord(
                    sn=norm_sn(raw_sn),
                    pn=norm_pn(pn),
                    host=host,
                    port=port,
                    source=source,
                    fmt="ipmitool_fru",
                    name=device or label,
                )
            )
    return records


def _lshw_serial(node: dict) -> str:
    for key in ("serial", "serial_number", "serialnumber"):
        raw = node.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if not is_placeholder_sn(text):
            return text
    return ""


def _lshw_pn(node: dict) -> str:
    for key in ("pn", "part_number", "product", "model"):
        raw = node.get(key)
        if raw:
            return norm_pn(str(raw))
    return ""


def _lshw_port(node: dict) -> str:
    for key in ("port", "slot", "logicalname", "id"):
        raw = node.get(key)
        if raw is None:
            continue
        port = canonicalize_port(str(raw))
        if port:
            return port
    return ""


def _walk_lshw(node, host: str, source: str, out: list[DumpRecord]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_lshw(item, host, source, out)
        return
    if not isinstance(node, dict):
        return
    next_host = host
    if node.get("hostname"):
        next_host = norm_host(str(node.get("hostname")))
    config = node.get("configuration")
    if isinstance(config, dict) and config.get("hostname"):
        next_host = norm_host(str(config.get("hostname")))
    raw_sn = _lshw_serial(node)
    if raw_sn:
        label = str(node.get("id") or node.get("description") or node.get("class") or "")
        out.append(
            DumpRecord(
                sn=norm_sn(raw_sn),
                pn=_lshw_pn(node),
                host=next_host,
                port=_lshw_port(node),
                source=source,
                fmt="lshw_json",
                name=label,
            )
        )
    for key in ("children", "child"):
        kids = node.get(key)
        if kids:
            _walk_lshw(kids, next_host, source, out)


def _parse_lshw(text: str, source: str) -> list[DumpRecord]:
    try:
        payload = json.loads(text.lstrip("\ufeff"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"lshw json is not valid: {exc}") from exc
    records: list[DumpRecord] = []
    _walk_lshw(payload, "", source, records)
    return records


def text_table(headers: list[str], rows: list[list[object]]) -> str:
    str_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for cells in str_rows:
        for index, cell in enumerate(cells):
            widths[index] = max(widths[index], len(cell))

    def fmt(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()

    lines = [fmt(headers), fmt(["-" * width for width in widths])]
    lines.extend(fmt(cells) for cells in str_rows)
    return "\n".join(lines)


def short_source(source: str) -> str:
    if not source:
        return ""
    path = Path(source)
    parts = path.parts
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return path.name
