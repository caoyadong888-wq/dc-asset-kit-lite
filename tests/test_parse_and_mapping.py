#!/usr/bin/env python3
"""Parsers, SN normalization, and each mapping finding."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sn_dump_parse import (  # noqa: E402
    norm_sn,
    parse_dump,
    parse_text,
)
from sn_mapping_check import (  # noqa: E402
    RegisterRecord,
    check_mapping,
    exit_code_for,
    load_register,
)


def _reg(asset_id, sn, pn, host, port, **kwargs):
    return RegisterRecord(
        asset_id=asset_id,
        sn=norm_sn(sn),
        pn=pn,
        host=host,
        port=port,
        asset_class=kwargs.get("asset_class", "optic"),
        rack=kwargs.get("rack", "A01"),
        u_position=kwargs.get("u_position", ""),
        status=kwargs.get("status", "in_service"),
        source=kwargs.get("source", "register.csv"),
    )


class ParseTests(unittest.TestCase):
    def test_cisco_parser_name_pid_sn_port(self):
        text = textwrap.dedent(
            """\
            dc1-rack-a01-sw01# show inventory
            NAME: "Chassis", DESCR: "Sample leaf chassis"
            PID: SMP-SW-48Y8C        , VID: V01 , SN: SYNSWCH0001

            NAME: "Transceiver Ethernet1/3", DESCR: "Sample optic SMP-SFP-10G-SR"
            PID: SMP-SFP-10G-SR      , VID: V01 , SN: synopt0003
            """
        )
        rows = parse_text(text, source="dumps/sw01_show_inventory.txt", hint="show_inventory.txt")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].fmt, "cisco_inventory")
        self.assertEqual(rows[0].sn, "SYNSWCH0001")
        self.assertEqual(rows[0].pn, "SMP-SW-48Y8C")
        self.assertEqual(rows[0].host, "dc1-rack-a01-sw01")
        self.assertEqual(rows[0].port, "")
        self.assertEqual(rows[1].sn, "SYNOPT0003")
        self.assertEqual(rows[1].port, "Ethernet1/3")
        self.assertEqual(rows[1].pn, "SMP-SFP-10G-SR")

    def test_cisco_skips_empty_and_placeholder_sn(self):
        text = textwrap.dedent(
            """\
            dc1-rack-a01-sw01# show inventory
            NAME: "Empty", DESCR: "no serial"
            PID: SMP-SW-SUP          , VID: V01 , SN:

            NAME: "Placeholder", DESCR: "oem"
            PID: SMP-SW-SUP          , VID: V01 , SN: To be filled by O.E.M.

            NAME: "Transceiver Ethernet1/1", DESCR: "kept"
            PID: SMP-SFP-10G-SR      , VID: V01 , SN: SYNOPT0001
            """
        )
        rows = parse_text(text, hint="inventory.txt")
        self.assertEqual([row.sn for row in rows], ["SYNOPT0001"])

    def test_ipmitool_fru_product_and_board_serials(self):
        text = textwrap.dedent(
            """\
            # host: dc1-rack-a01-srv01
            # command: ipmitool fru print

            FRU Device Description : NIC1 (ID 1)
             Board Serial          : SYNBOARD001
             Board Part Number     : SMP-BOARD-1
             Product Name          : SMP-SFP-10G-SR
             Product Part Number   : SMP-SFP-10G-SR
             Product Serial        : SYNOPT0015

            FRU Device Description : PSU1 (ID 2)
             Product Part Number   : SMP-PSU-800
             Product Serial        : 0000000000
            """
        )
        rows = parse_text(text, hint="srv01_ipmitool_fru.txt")
        self.assertEqual(rows[0].fmt, "ipmitool_fru")
        self.assertEqual([(row.sn, row.pn, row.port, row.host) for row in rows], [
            ("SYNBOARD001", "SMP-BOARD-1", "NIC1", "dc1-rack-a01-srv01"),
            ("SYNOPT0015", "SMP-SFP-10G-SR", "NIC1", "dc1-rack-a01-srv01"),
        ])

    def test_lshw_nested_serials_and_hostname(self):
        text = textwrap.dedent(
            """\
            {
              "id": "system",
              "class": "system",
              "product": "Sample Server R2",
              "configuration": {"hostname": "dc1-rack-a01-srv02"},
              "children": [
                {"id": "memory", "class": "memory", "description": "System Memory"},
                {
                  "id": "nic1",
                  "class": "network",
                  "product": "SMP-SFP-10G-LR",
                  "serial": "synopt0017",
                  "port": "NIC1"
                }
              ]
            }
            """
        )
        rows = parse_text(text, hint="srv02_lshw.json")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].fmt, "lshw_json")
        self.assertEqual(rows[0].sn, "SYNOPT0017")
        self.assertEqual(rows[0].pn, "SMP-SFP-10G-LR")
        self.assertEqual(rows[0].host, "dc1-rack-a01-srv02")
        self.assertEqual(rows[0].port, "NIC1")

    def test_autodetect_formats(self):
        cisco = 'NAME: "Chassis", DESCR: "box"\nPID: SMP-SW , VID: V01 , SN: ABC123\n'
        fru = "FRU Device Description : NIC1 (ID 1)\n Product Serial : ABC123\n Product Part Number : SMP\n"
        lshw = '{"id":"system","serial":"ABC123","product":"SMP","configuration":{"hostname":"dc1-rack-a01-srv02"}}'
        self.assertEqual(parse_text(cisco)[0].fmt, "cisco_inventory")
        self.assertEqual(parse_text(fru)[0].fmt, "ipmitool_fru")
        self.assertEqual(parse_text(lshw)[0].fmt, "lshw_json")

    def test_sn_normalization_strip_upper(self):
        self.assertEqual(norm_sn("  synopt0002 "), "SYNOPT0002")
        self.assertEqual(norm_sn("Ab 12"), "AB 12")


class FindingTests(unittest.TestCase):
    def test_finding_missing(self):
        findings = check_mapping(
            [_reg("OPT-MISS", "SYNMISSOPT0001", "SMP-SFP-10G-LR", "dc1-rack-a01-sw01", "Ethernet1/48")],
            [],
        )
        self.assertEqual([item.type for item in findings], ["MISSING"])
        self.assertEqual(findings[0].severity, "high")
        self.assertIn("not in dumps", findings[0].detail)

    def test_finding_unknown(self):
        dump = parse_text(
            'dc1-rack-a01-sw01# show inventory\n'
            'NAME: "Transceiver Ethernet1/40", DESCR: "extra"\n'
            "PID: SMP-SFP28-25G-SR , VID: V01 , SN: SYNUNKOPT9001\n",
            source="dumps/sw01_show_inventory.txt",
        )
        findings = check_mapping([], dump)
        self.assertEqual([item.type for item in findings], ["UNKNOWN"])
        self.assertEqual(findings[0].sn, "SYNUNKOPT9001")
        self.assertEqual(findings[0].severity, "medium")

    def test_finding_duplicate(self):
        rows = [
            _reg("OPT-0042A", "SYNDUPOPT0042", "SMP-SFP-10G-SR", "dc1-rack-a01-sw01", "Ethernet1/22"),
            _reg("OPT-0042B", " syndupopt0042 ", "SMP-SFP-10G-SR", "dc1-rack-a01-sw01", "Ethernet1/22"),
        ]
        dump = parse_text(
            'dc1-rack-a01-sw01# show inventory\n'
            'NAME: "Transceiver Ethernet1/22", DESCR: "dup"\n'
            "PID: SMP-SFP-10G-SR , VID: V01 , SN: SYNDUPOPT0042\n"
        )
        findings = check_mapping(rows, dump)
        self.assertEqual([item.type for item in findings], ["DUPLICATE"])
        self.assertEqual(findings[0].asset_ids, ["OPT-0042A", "OPT-0042B"])

    def test_duplicate_does_not_imply_mismatch_when_dump_agrees(self):
        rows = [
            _reg("OPT-0042A", "SYNDUPOPT0042", "SMP-SFP-10G-SR", "dc1-rack-a01-sw01", "Ethernet1/22"),
            _reg("OPT-0042B", "SYNDUPOPT0042", "SMP-SFP-10G-SR", "dc1-rack-a01-sw01", "Ethernet1/22"),
        ]
        dump = parse_text(
            'dc1-rack-a01-sw01# show inventory\n'
            'NAME: "Transceiver Ethernet1/22", DESCR: "dup"\n'
            "PID: SMP-SFP-10G-SR , VID: V01 , SN: SYNDUPOPT0042\n"
        )
        types = {item.type for item in check_mapping(rows, dump)}
        self.assertEqual(types, {"DUPLICATE"})

    def test_finding_mismatch_location(self):
        rows = [_reg("OPT-0100", "SYNLOCOPT0100", "SMP-QSFP28-100G-LR4", "dc1-rack-a01-sw01", "Ethernet1/20")]
        dump = parse_text(
            'dc1-rack-a01-sw01# show inventory\n'
            'NAME: "Transceiver Ethernet1/28", DESCR: "moved"\n'
            "PID: SMP-QSFP28-100G-LR4 , VID: V01 , SN: SYNLOCOPT0100\n"
        )
        findings = check_mapping(rows, dump)
        self.assertEqual([item.type for item in findings], ["MISMATCH_LOCATION"])
        self.assertIn("Ethernet1/20", findings[0].detail)
        self.assertIn("Ethernet1/28", findings[0].detail)

    def test_finding_mismatch_pn(self):
        rows = [_reg("OPT-0200", "SYNPNOPT0200", "SMP-QSFP28-100G-SR4", "dc1-rack-a01-sw01", "Ethernet1/21")]
        dump = parse_text(
            'dc1-rack-a01-sw01# show inventory\n'
            'NAME: "Transceiver Ethernet1/21", DESCR: "other pn"\n'
            "PID: SMP-QSFP28-100G-CWDM4 , VID: V01 , SN: SYNPNOPT0200\n"
        )
        findings = check_mapping(rows, dump)
        self.assertEqual([item.type for item in findings], ["MISMATCH_PN"])
        self.assertIn("SMP-QSFP28-100G-SR4", findings[0].detail)
        self.assertIn("SMP-QSFP28-100G-CWDM4", findings[0].detail)

    def test_clean_input_has_no_findings(self):
        rows = [_reg("OPT-0003", "SYNOPT0003", "SMP-SFP-10G-SR", "DC1-RACK-A01-SW01", "ethernet1/3")]
        dump = parse_text(
            'dc1-rack-a01-sw01# show inventory\n'
            'NAME: "Transceiver Ethernet1/3", DESCR: "ok"\n'
            "PID: smp-sfp-10g-sr , VID: V01 , SN:  synopt0003 \n"
        )
        findings = check_mapping(rows, dump)
        self.assertEqual(findings, [])
        self.assertEqual(exit_code_for(findings), 0)

    def test_switch_model_mismatch_ignores_chassis_name(self):
        rows = [_reg(
            "SW-0001", "SYNSWCH0001", "SMP-SW-OTHER", "dc1-rack-a01-sw01", "",
            asset_class="switch",
        )]
        dump = parse_text(
            'dc1-rack-a01-sw01# show inventory\n'
            'NAME: "Chassis", DESCR: "leaf"\n'
            "PID: SMP-SW-48Y8C , VID: V01 , SN: SYNSWCH0001\n"
        )
        findings = check_mapping(rows, dump)
        self.assertEqual([item.type for item in findings], ["MISMATCH_PN"])

    def test_whitespace_register_sn_matches_dump(self):
        rows = [_reg("OPT-0002", " SYNOPT0002 ", "SMP-SFP-1G-LX", "dc1-rack-a01-sw01", "Ethernet1/2")]
        dump = parse_text(
            'dc1-rack-a01-sw01# show inventory\n'
            'NAME: "Transceiver Ethernet1/2", DESCR: "pad"\n'
            "PID: SMP-SFP-1G-LX , VID: V01 , SN: SYNOPT0002\n"
        )
        self.assertEqual(check_mapping(rows, dump), [])

    def test_cli_exit_codes(self):
        script = ROOT / "scripts" / "sn_mapping_check.py"
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            register = folder / "register.csv"
            register.write_text(
                "asset_id,sn,pn,vendor,type,speed,wavelength,reach,host,port,rack,status,install_date\n"
                "OPT-0001,SYNOPT0001,SMP-SFP-10G-SR,HarborOptic,SFP+,10G,850nm,300m,"
                "dc1-rack-a01-sw01,Ethernet1/1,A01,in_service,2026-04-01\n",
                encoding="utf-8",
            )
            dump = folder / "sw_show_inventory.txt"
            dump.write_text(
                'dc1-rack-a01-sw01# show inventory\n'
                'NAME: "Transceiver Ethernet1/1", DESCR: "ok"\n'
                "PID: SMP-SFP-10G-SR , VID: V01 , SN: SYNOPT0001\n",
                encoding="utf-8",
            )
            out = folder / "out"
            clean = subprocess.run(
                [sys.executable, str(script), "--register", str(register), "--dumps", str(dump), "--out", str(out)],
                cwd=folder,
                capture_output=True,
                text=True,
            )
            self.assertEqual(clean.returncode, 0, clean.stderr)
            self.assertTrue((out / "report.md").is_file())
            self.assertTrue((out / "report.csv").is_file())
            self.assertTrue((out / "report.json").is_file())
            dump.write_text(
                dump.read_text(encoding="utf-8")
                + 'NAME: "Transceiver Ethernet1/40", DESCR: "extra"\n'
                + "PID: SMP-SFP28-25G-SR , VID: V01 , SN: SYNUNKOPT9001\n",
                encoding="utf-8",
            )
            dirty = subprocess.run(
                [sys.executable, str(script), "--register", str(register), "--dumps", str(dump), "--out", str(out)],
                cwd=folder,
                capture_output=True,
                text=True,
            )
            self.assertEqual(dirty.returncode, 2, dirty.stderr)
            self.assertIn("UNKNOWN", dirty.stdout)


class SamplePackTests(unittest.TestCase):
    def test_sample_dump_record_counts(self):
        dumps = ROOT / "samples" / "dumps"
        inventory = parse_dump(dumps / "sw01_show_inventory.txt")
        fru = parse_dump(dumps / "srv01_ipmitool_fru.txt")
        lshw = parse_dump(dumps / "srv02_lshw.json")
        self.assertEqual(len(inventory), 32)
        self.assertEqual(len(fru), 4)
        self.assertEqual(len(lshw), 3)
        self.assertEqual({row.fmt for row in inventory}, {"cisco_inventory"})
        self.assertEqual({row.fmt for row in fru}, {"ipmitool_fru"})
        self.assertEqual({row.fmt for row in lshw}, {"lshw_json"})
        self.assertEqual({row.host for row in inventory}, {"dc1-rack-a01-sw01"})
        self.assertEqual({row.host for row in fru}, {"dc1-rack-a01-srv01"})
        self.assertEqual({row.host for row in lshw}, {"dc1-rack-a01-srv02"})

    def test_sample_pack_exact_findings(self):
        register = load_register([
            str(ROOT / "samples" / "register" / "asset_register_aoc.csv"),
            str(ROOT / "samples" / "register" / "asset_register_optics.csv"),
            str(ROOT / "samples" / "register" / "asset_register_switches.csv"),
        ])
        self.assertEqual(len(register), 40)
        dumps = []
        for path in sorted((ROOT / "samples" / "dumps").glob("*")):
            if path.is_file():
                dumps.extend(parse_dump(path))
        findings = check_mapping(register, dumps)
        grouped = {}
        for item in findings:
            grouped.setdefault(item.type, []).append(item.sn)
        self.assertEqual(grouped["MISSING"], ["SYNMISSAOC0002", "SYNMISSOPT0001"])
        self.assertEqual(grouped["UNKNOWN"], ["SYNUNKFRU9002", "SYNUNKOPT9001"])
        self.assertEqual(grouped["DUPLICATE"], ["SYNDUPOPT0042"])
        self.assertEqual(grouped["MISMATCH_LOCATION"], ["SYNLOCOPT0100"])
        self.assertEqual(grouped["MISMATCH_PN"], ["SYNPNOPT0200"])
        self.assertEqual(exit_code_for(findings), 2)
        padded = [row for row in register if row.asset_id == "OPT-0002"]
        self.assertEqual(padded[0].sn, "SYNOPT0002")
        self.assertTrue(all(item.sn != "SYNOPT0001" for item in findings))
        dup = next(item for item in findings if item.type == "DUPLICATE")
        self.assertEqual(dup.asset_ids, ["OPT-0042A", "OPT-0042B"])


if __name__ == "__main__":
    unittest.main()
