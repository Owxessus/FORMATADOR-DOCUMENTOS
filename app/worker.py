# -*- coding: utf-8 -*-
"""Processamento em segundo plano: decide o motor e executa o pipeline."""
from __future__ import annotations

import datetime
import os
import threading

import ai_client
import archive
import checks
import docx_engine
import memory
import settings
import xlsx_engine


class Job(threading.Thread):
    """Processa um arquivo; comunica progresso/resultado via callbacks
    (chamados a partir da thread — a UI deve re-postar com .after())."""

    def __init__(self, path: str, cfg: dict, extra: str,
                 on_progress, on_done, on_error, want_pdf: bool = False,
                 perfil: str = "Detectar automaticamente"):
        super().__init__(daemon=True)
        self.want_pdf = want_pdf
        self.perfil = perfil
        self.path = path
        self.cfg = cfg
        self.extra = extra
        self.on_progress = on_progress
        self.on_done = on_done
        self.on_error = on_error

    def run(self):
        try:
            client = ai_client.OpenRouterClient(
                self.cfg["api_key"], model=self.cfg["model"])

            protected = self.cfg.get("protected_terms") or []

            def corrector(texts, kinds, extra):
                return client.corrector(texts, kinds, extra,
                                        progress=self.on_progress,
                                        protected=protected)

            ext = os.path.splitext(self.path)[1].lower()
            out_dir = self.cfg.get("out_dir") or None
            if ext == ".docx":
                mem = memory.load()
                paras = docx_engine.extract(self.path).editable_texts
                nome_perfil = self.perfil
                if nome_perfil == "Detectar automaticamente":
                    nome_perfil = memory.detectar_perfil(paras, mem)
                perfil = mem["perfis"].get(nome_perfil, {})

                extra = self.extra
                if perfil.get("instrucoes"):
                    extra = (extra + " " + perfil["instrucoes"]).strip()

                blocos = {n: t for n, t in mem.get("blocos", {}).items()
                          if not perfil.get("blocos")
                          or n in perfil["blocos"]}
                verificadores = [
                    checks.check_dates,
                    lambda ps: checks.check_canonical(ps, blocos),
                ]
                res = docx_engine.process(
                    self.path, corrector, out_dir=out_dir,
                    extra_instructions=extra, progress=self.on_progress,
                    signature_labels=perfil.get("assinatura") or None,
                    checkers=verificadores)
                res["perfil"] = nome_perfil
            elif ext == ".xlsx":
                res = xlsx_engine.process(
                    self.path, corrector, out_dir=out_dir,
                    extra_instructions=self.extra, progress=self.on_progress)
            else:
                raise ValueError(
                    "Formato não suportado. Use arquivos .docx ou .xlsx.")

            res["cost"] = client.total_cost
            res["pdf"] = None
            if ext == ".docx" and self.want_pdf:
                res["pdf"] = self._try_pdf(res["final"])

            try:   # arquivo pesquisável
                self.on_progress("Indexando para a busca…")
                archive.indexar(res["final"], perfil=res.get("perfil", ""),
                                texto=res.get("texto"))
            except Exception:  # noqa: BLE001 — busca nunca bloqueia a entrega
                pass

            settings.add_history(self.cfg, {
                "file": os.path.basename(self.path),
                "when": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                "cost": round(res["cost"], 4),
                "changed": res.get("changed", 0),
            })
            self.on_done(res)
        except Exception as e:  # noqa: BLE001 — erro vai para a UI
            self.on_error(str(e))

    def _try_pdf(self, docx_path: str) -> str | None:
        """Exporta PDF via Word instalado (docx2pdf); silencioso se faltar."""
        try:
            self.on_progress("Gerando PDF…")
            from docx2pdf import convert
            pdf_path = os.path.splitext(docx_path)[0] + ".pdf"
            convert(docx_path, pdf_path)
            return pdf_path if os.path.exists(pdf_path) else None
        except Exception:  # noqa: BLE001
            self.on_progress("PDF indisponível (Word não encontrado).")
            return None
