# -*- coding: utf-8 -*-
"""Processamento em segundo plano: decide o motor e executa o pipeline."""
from __future__ import annotations

import datetime
import os
import threading

import ai_client
import docx_engine
import settings
import xlsx_engine


class Job(threading.Thread):
    """Processa um arquivo; comunica progresso/resultado via callbacks
    (chamados a partir da thread — a UI deve re-postar com .after())."""

    def __init__(self, path: str, cfg: dict, extra: str,
                 on_progress, on_done, on_error, want_pdf: bool = False):
        super().__init__(daemon=True)
        self.want_pdf = want_pdf
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
                res = docx_engine.process(
                    self.path, corrector, out_dir=out_dir,
                    extra_instructions=self.extra, progress=self.on_progress)
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
