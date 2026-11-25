#!/usr/bin/env python3
"""Bandingkan netlist hasil export KiCad dengan netlist yang dimaksud generator.

    kicad-cli sch export netlist -o /tmp/bms.net kicad/bms.kicad_sch
    python3 tools/check_netlist.py /tmp/bms.net
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_schematic as G  # noqa: E402

net_txt = open(sys.argv[1]).read()
kicad = {}
for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "([^"]*)"\)(.*?)\)\s*(?=\(net |\)\s*\)\s*$)', net_txt, re.S):
    name, body = m.group(1), m.group(2)
    nodes = frozenset(f"{r}.{p}" for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', body))
    nodes = frozenset(n for n in nodes if not n.startswith("#"))
    if nodes:
        kicad[nodes] = name

G.build()
errs, netconn, netsheets = G.intended()
want = {}
for net, conns in netconn.items():
    s = frozenset(conns)
    if s:
        want[s] = net

ok = True
for s, net in want.items():
    if s not in kicad:
        ok = False
        print(f"HILANG/BEDA: {net}: {sorted(s)}")
        for ks, kn in kicad.items():
            if ks & s:
                print(f"    kicad {kn}: {sorted(ks)}")
for s, kn in kicad.items():
    if s not in want and len(s) > 1 and not kn.startswith("unconnected-"):
        ok = False
        print(f"NET TAK TERDUGA di KiCad: {kn}: {sorted(s)}")
singles = [kn for s, kn in kicad.items() if s not in want and len(s) == 1]
print(f"KiCad: {len(kicad)} net, generator: {len(want)} net; pin unconnected (NC) di KiCad: {len(singles)}")
print("COCOK" if ok else "ADA PERBEDAAN")
sys.exit(0 if ok else 1)
