# -*- coding: utf-8 -*-
"""Teste do motor com os 4 relatórios reais e corretor simulado
(usa as correções feitas manualmente na sessão como gabarito)."""
import difflib
import re
import sys

sys.path.insert(0, "/home/claude/formatador-relatorios/app")
sys.path.insert(0, "/home/claude/relatorios")

import docx_engine as eng


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def make_mock(units):
    """corrector() que casa cada parágrafo extraído com o gabarito manual."""
    pairs = [(norm(o), c) for _, o, c in units]

    def corrector(texts, kinds, extra):
        out = []
        for t in texts:
            nt = norm(t).lstrip("•").strip()
            best, score = None, 0.0
            for o, c in pairs:
                s = difflib.SequenceMatcher(None, nt, o).ratio()
                if s > score:
                    best, score = c, s
            out.append(best if score > 0.75 else t)
        return out
    return corrector


CASES = [
    ("vivian",   "/home/claude/relatorios/vivian_original.docx",   "content_vivian"),
    ("maria",    "/home/claude/relatorios/maria_original.docx",    "content_maria"),
    ("pamela",   "/home/claude/relatorios/pamela_original.docx",   "content_pamela"),
    ("caroliny", "/home/claude/relatorios/caroliny_original.docx", "content_caroliny"),
]

ok_all = True
for name, path, mod in CASES:
    units = __import__(mod).UNITS
    res = eng.process(path, make_mock(units),
                      out_dir="/home/claude/formatador-relatorios/tests/out",
                      progress=lambda m: None)
    status = "OK " if res["verified"] else "FAIL"
    ok_all &= res["verified"]
    print(f"[{status}] {name}: {res['paragraphs']} parágrafos, "
          f"{res['changed']} alterados, avisos={len(res['warnings'])}")
    for w in res["warnings"]:
        print("        aviso:", w[:100])

print("\nRESULTADO GERAL:", "PASSOU" if ok_all else "FALHOU")
sys.exit(0 if ok_all else 1)
