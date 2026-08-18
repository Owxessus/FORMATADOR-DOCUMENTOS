# -*- coding: utf-8 -*-
"""Formatador de Relatórios — app desktop.

Modo widget (padrão): janelinha compacta, sempre por cima, só com a área de
soltar arquivo. Modo janela: histórico + configurações. Botão ⤢ alterna.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

import ai_client
import settings
import worker

APP_TITLE = "Formatador de Relatórios"
WIDGET_SIZE = "360x330"
FULL_SIZE = "820x560"

ACCENT = "#2B6CB0"
ACCENT_HOVER = "#255EA0"
OK_COLOR = "#2F855A"
ERR_COLOR = "#C53030"


def open_folder(path: str) -> None:
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if sys.platform == "win32":
        os.startfile(folder)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = settings.load()
        ctk.set_appearance_mode(self.cfg.get("theme", "light"))
        ctk.set_default_color_theme("blue")

        self.title(APP_TITLE)
        self.minsize(340, 300)
        self.widget_mode = True
        self.busy = False
        self._apply_window_mode(initial=True)

        self.container = ctk.CTkFrame(self, corner_radius=0,
                                      fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        if not self.cfg.get("onboarded"):
            self._show_onboarding()
        else:
            self._show_main()

    # ------------------------------------------------------------- janela

    def _apply_window_mode(self, initial=False):
        self.geometry(WIDGET_SIZE if self.widget_mode else FULL_SIZE)
        top = bool(self.cfg.get("always_on_top", True)) and self.widget_mode
        self.attributes("-topmost", top)
        if not initial:
            self._show_main()

    def _toggle_mode(self):
        self.widget_mode = not self.widget_mode
        self._apply_window_mode()

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    # -------------------------------------------------------- onboarding

    def _show_onboarding(self, step: int = 1):
        self._clear()
        self.widget_mode = False
        self.geometry("560x430")
        self.attributes("-topmost", False)
        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        if step == 1:
            ctk.CTkLabel(frame, text="👋  Bem-vinda!",
                         font=ctk.CTkFont(size=26, weight="bold")).pack(pady=(30, 12))
            ctk.CTkLabel(
                frame, wraplength=460, justify="center",
                font=ctk.CTkFont(size=15),
                text=("Este app pega um relatório (.docx) bruto, corrige "
                      "ortografia e coerência com IA — sem mudar o conteúdo — "
                      "e devolve duas versões prontas:\n\n"
                      "📄  FINAL, formatada no padrão institucional\n"
                      "📝  ALTERAÇÕES RASTREADAS, para revisar cada mudança "
                      "no Word\n\nTudo é salvo ao lado do arquivo original."),
            ).pack(pady=8)
            ctk.CTkButton(frame, text="Começar  →", height=44, width=200,
                          fg_color=ACCENT, hover_color=ACCENT_HOVER,
                          font=ctk.CTkFont(size=15, weight="bold"),
                          command=lambda: self._show_onboarding(2)).pack(pady=26)

        elif step == 2:
            ctk.CTkLabel(frame, text="🔑  Sua chave OpenRouter",
                         font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(16, 8))
            ctk.CTkLabel(
                frame, wraplength=460, justify="center",
                text=("1. Crie uma conta gratuita em openrouter.ai\n"
                      "2. Em “Keys”, crie uma chave e copie\n"
                      "3. Em “Credits”, adicione créditos (US$ 5 rendem "
                      "dezenas de relatórios)\n4. Cole a chave abaixo:")).pack(pady=6)
            self.key_entry = ctk.CTkEntry(frame, width=420, height=40,
                                          placeholder_text="sk-or-v1-…",
                                          show="•")
            self.key_entry.pack(pady=10)
            self.key_entry.insert(0, self.cfg.get("api_key", ""))
            self.key_status = ctk.CTkLabel(frame, text="", wraplength=460)
            self.key_status.pack(pady=4)
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(pady=12)
            ctk.CTkButton(row, text="Testar conexão", height=40,
                          fg_color="gray50", command=self._test_key).pack(
                side="left", padx=6)
            self.key_next = ctk.CTkButton(
                row, text="Continuar  →", height=40, state="disabled",
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                command=lambda: self._show_onboarding(3))
            self.key_next.pack(side="left", padx=6)

        else:
            ctk.CTkLabel(frame, text="⚙️  Preferências",
                         font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(16, 10))
            ctk.CTkLabel(frame, text="Gerar PDF da versão final?").pack(pady=(8, 2))
            self.pdf_var = ctk.StringVar(value=self.cfg.get("generate_pdf",
                                                            "perguntar"))
            ctk.CTkSegmentedButton(frame, values=["sempre", "perguntar", "nunca"],
                                   variable=self.pdf_var).pack(pady=4)
            self.top_var = ctk.BooleanVar(
                value=self.cfg.get("always_on_top", True))
            ctk.CTkCheckBox(frame, text="Widget sempre visível por cima "
                            "das outras janelas", variable=self.top_var).pack(pady=14)
            ctk.CTkLabel(frame, wraplength=460, text_color="gray",
                         text=("Dica de privacidade: na sua conta OpenRouter, "
                               "em Settings → Privacy, desative o uso dos seus "
                               "dados para treinamento.")).pack(pady=6)
            ctk.CTkButton(frame, text="Concluir  ✓", height=44, width=200,
                          fg_color=OK_COLOR,
                          font=ctk.CTkFont(size=15, weight="bold"),
                          command=self._finish_onboarding).pack(pady=18)

    def _test_key(self):
        key = self.key_entry.get().strip()
        if not key:
            self.key_status.configure(text="Cole a chave primeiro.",
                                      text_color=ERR_COLOR)
            return
        self.key_status.configure(text="Testando…", text_color="gray")

        def check():
            try:
                data = ai_client.OpenRouterClient(key).validate_key()
                usage = data.get("usage")
                limit = data.get("limit")
                saldo = ""
                if limit is not None and usage is not None:
                    saldo = f"  Saldo: US$ {max(limit - usage, 0):.2f}"
                self.after(0, lambda: (
                    self.key_status.configure(
                        text=f"✓ Chave válida!{saldo}", text_color=OK_COLOR),
                    self.key_next.configure(state="normal")))
            except Exception as e:  # noqa: BLE001
                self.after(0, lambda: self.key_status.configure(
                    text=f"✗ {e}", text_color=ERR_COLOR))

        threading.Thread(target=check, daemon=True).start()

    def _finish_onboarding(self):
        self.cfg["api_key"] = self.key_entry.get().strip() \
            if hasattr(self, "key_entry") else self.cfg["api_key"]
        self.cfg["generate_pdf"] = self.pdf_var.get()
        self.cfg["always_on_top"] = bool(self.top_var.get())
        self.cfg["onboarded"] = True
        settings.save(self.cfg)
        self.widget_mode = True
        self._apply_window_mode()

    # ------------------------------------------------------------- main UI

    def _show_main(self):
        self._clear()
        outer = ctk.CTkFrame(self.container, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        # barra do topo
        bar = ctk.CTkFrame(outer, fg_color="transparent")
        bar.pack(fill="x")
        ctk.CTkLabel(bar, text="Formatador",
                     font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
        ctk.CTkButton(bar, text="⤢" if self.widget_mode else "⤡", width=34,
                      height=28, fg_color="gray70",
                      command=self._toggle_mode).pack(side="right")

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=(8, 0))

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        # área de drop
        self.drop = ctk.CTkFrame(left, corner_radius=16,
                                 border_width=2, border_color=ACCENT)
        self.drop.pack(fill="both", expand=True)
        self.drop_label = ctk.CTkLabel(
            self.drop, justify="center",
            font=ctk.CTkFont(size=15, weight="bold"),
            text="📄\n\nSolte o relatório aqui\n(.docx ou .xlsx)")
        self.drop_label.place(relx=0.5, rely=0.42, anchor="center")
        ctk.CTkButton(self.drop, text="ou clique para escolher",
                      fg_color="transparent", text_color=ACCENT,
                      hover=False, command=self._pick_file).place(
            relx=0.5, rely=0.72, anchor="center")

        self.drop.drop_target_register(DND_FILES)
        self.drop.dnd_bind("<<Drop>>", self._on_drop)

        # instruções extras + status
        self.extra_entry = ctk.CTkEntry(
            left, placeholder_text="Instruções adicionais (opcional)",
            height=34)
        self.extra_entry.pack(fill="x", pady=(8, 4))

        self.progress = ctk.CTkProgressBar(left, mode="indeterminate",
                                           height=8)
        self.status = ctk.CTkLabel(left, text="", wraplength=320,
                                   font=ctk.CTkFont(size=12))
        self.status.pack(fill="x")
        self.open_btn = ctk.CTkButton(left, text="📂  Abrir pasta",
                                      fg_color=OK_COLOR, height=34,
                                      command=lambda: None)

        # painel lateral (modo janela)
        if not self.widget_mode:
            right = ctk.CTkFrame(body, width=360)
            right.pack(side="right", fill="both", padx=(12, 0))
            tabs = ctk.CTkTabview(right, width=350)
            tabs.pack(fill="both", expand=True, padx=6, pady=6)
            self._build_history_tab(tabs.add("Histórico"))
            self._build_settings_tab(tabs.add("Configurações"))

    def _build_history_tab(self, tab):
        frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        hist = self.cfg.get("history", [])
        if not hist:
            ctk.CTkLabel(frame, text="Nenhum documento processado ainda.",
                         text_color="gray").pack(pady=20)
        for h in hist:
            card = ctk.CTkFrame(frame, corner_radius=10)
            card.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(card, text=h["file"], anchor="w",
                         font=ctk.CTkFont(weight="bold")).pack(
                fill="x", padx=10, pady=(6, 0))
            ctk.CTkLabel(card, anchor="w", text_color="gray",
                         text=(f'{h["when"]}  ·  {h["changed"]} correções  ·  '
                               f'US$ {h["cost"]:.3f}')).pack(
                fill="x", padx=10, pady=(0, 6))

    def _build_settings_tab(self, tab):
        frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        frame.pack(fill="both", expand=True)

        def field(label):
            ctk.CTkLabel(frame, text=label, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(
                fill="x", pady=(10, 2))

        field("Chave OpenRouter")
        key = ctk.CTkEntry(frame, show="•")
        key.pack(fill="x")
        key.insert(0, self.cfg.get("api_key", ""))

        field("Modelo de IA")
        model = ctk.CTkEntry(frame)
        model.pack(fill="x")
        model.insert(0, self.cfg.get("model", ai_client.DEFAULT_MODEL))

        field("Gerar PDF da versão final")
        pdf = ctk.CTkSegmentedButton(frame,
                                     values=["sempre", "perguntar", "nunca"])
        pdf.set(self.cfg.get("generate_pdf", "perguntar"))
        pdf.pack(fill="x")

        top_var = ctk.BooleanVar(value=self.cfg.get("always_on_top", True))
        ctk.CTkCheckBox(frame, text="Widget sempre por cima",
                        variable=top_var).pack(anchor="w", pady=10)

        theme_var = ctk.StringVar(value=self.cfg.get("theme", "light"))
        field("Tema")
        ctk.CTkSegmentedButton(frame, values=["light", "dark"],
                               variable=theme_var).pack(fill="x")

        def save_all():
            self.cfg.update(api_key=key.get().strip(),
                            model=model.get().strip() or ai_client.DEFAULT_MODEL,
                            generate_pdf=pdf.get(),
                            always_on_top=bool(top_var.get()),
                            theme=theme_var.get())
            settings.save(self.cfg)
            ctk.set_appearance_mode(theme_var.get())
            saved.configure(text="✓ Salvo")
            self.after(2000, lambda: saved.configure(text=""))

        ctk.CTkButton(frame, text="Salvar configurações", fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=save_all).pack(pady=14)
        saved = ctk.CTkLabel(frame, text="", text_color=OK_COLOR)
        saved.pack()

    # -------------------------------------------------------- processamento

    def _pick_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Escolha o documento",
            filetypes=[("Documentos", "*.docx *.xlsx")])
        if path:
            self._start(path)

    def _on_drop(self, event):
        raw = event.data.strip()
        path = raw[1:-1] if raw.startswith("{") and raw.endswith("}") else \
            raw.split()[0]
        self._start(path)

    def _start(self, path: str):
        if self.busy:
            return
        if not os.path.isfile(path):
            self._set_status(f"Arquivo não encontrado: {path}", ERR_COLOR)
            return
        if not self.cfg.get("api_key"):
            self._set_status("Configure a chave OpenRouter primeiro "
                             "(modo janela → Configurações).", ERR_COLOR)
            return
        self.busy = True
        self.open_btn.pack_forget()
        self.drop_label.configure(text="⏳\n\nProcessando…")
        self.progress.pack(fill="x", pady=(4, 2))
        self.progress.start()
        self._set_status("Iniciando…", "gray")

        job = worker.Job(
            path, self.cfg, self.extra_entry.get().strip(),
            on_progress=lambda m: self.after(0, self._set_status, m, "gray"),
            on_done=lambda r: self.after(0, self._done, r),
            on_error=lambda e: self.after(0, self._fail, e))
        job.start()

    def _set_status(self, msg: str, color: str = "gray"):
        self.status.configure(text=msg, text_color=color)

    def _done(self, res: dict):
        self.busy = False
        self.progress.stop()
        self.progress.pack_forget()
        self.drop_label.configure(
            text="✅\n\nPronto! Solte outro arquivo\nquando quiser")
        extra = f"  ·  US$ {res['cost']:.3f}" if res.get("cost") else ""
        warn = f"\n⚠ {len(res['warnings'])} aviso(s) — veja o diff." \
            if res.get("warnings") else ""
        self._set_status(
            f"✓ {res['changed']} correções em {res['paragraphs']} "
            f"parágrafos{extra}{warn}",
            OK_COLOR if res.get("verified") else ERR_COLOR)
        self.open_btn.configure(
            command=lambda: open_folder(res["final"]))
        self.open_btn.pack(fill="x", pady=(4, 0))

    def _fail(self, err: str):
        self.busy = False
        self.progress.stop()
        self.progress.pack_forget()
        self.drop_label.configure(
            text="📄\n\nSolte o relatório aqui\n(.docx ou .xlsx)")
        self._set_status(f"✗ {err}", ERR_COLOR)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
