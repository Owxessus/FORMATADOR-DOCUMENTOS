# -*- coding: utf-8 -*-
"""Formatador de Relatórios — app desktop.

Modo widget (padrão): janelinha compacta, sempre por cima, só com a área de
soltar arquivo. Modo janela: histórico + configurações. Botão ⤢ alterna.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

import ai_client
import archive
import forms
import memory
import outdir
import settings
import updater
import version
import worker

APP_TITLE = f"Formatador de Relatórios  v{version.VERSION}"
WIDGET_SIZE = "380x580"
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
        self._geom_job = None
        self.widget_mode = True
        self.busy = False
        self.queue: list[str] = []
        self.last_path: str | None = None
        self.update_info: dict | None = None
        self._apply_window_mode(initial=True)

        self.container = ctk.CTkFrame(self, corner_radius=0,
                                      fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        if not self.cfg.get("onboarded"):
            self._show_onboarding()
        else:
            self._show_main()
        self.bind("<Configure>", self._guardar_geometria)
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        if self.cfg.get("check_updates", True):
            self._checar_atualizacao()

    # -------------------------------------------------------- atualização

    def _checar_atualizacao(self, avisar_sem_novidade=False):
        def tarefa():
            try:
                info = updater.checar()
                self.after(0, self._resultado_atualizacao, info,
                           avisar_sem_novidade)
            except Exception:  # noqa: BLE001 — checagem é acessório
                pass
        threading.Thread(target=tarefa, daemon=True).start()

    def _resultado_atualizacao(self, info, avisar):
        self.update_info = info
        if info and self.cfg.get("onboarded"):
            self._show_main()
        elif avisar:
            self._set_status("Você já está na versão mais recente.", OK_COLOR)

    def _atualizar_agora(self):
        info = self.update_info
        if not info:
            return
        if not info.get("url") or not getattr(sys, "frozen", False):
            import webbrowser
            webbrowser.open(updater.PAGINA)
            return
        self._set_status("Atualizando…", "gray")

        def tarefa():
            try:
                updater.baixar_e_instalar(
                    info["url"],
                    progresso=lambda m: self.after(0, self._set_status, m,
                                                   "gray"))
            except Exception as e:  # noqa: BLE001
                self.after(0, self._set_status, f"✗ {e}", ERR_COLOR)
        threading.Thread(target=tarefa, daemon=True).start()

    # ------------------------------------------------------------- janela

    # ------------------------------------------------ posição e tamanho

    def _chave_geom(self) -> str:
        return "geom_widget" if self.widget_mode else "geom_janela"

    def _guardar_geometria(self, _evt=None):
        """Lembra onde a janela está e de que tamanho ficou (com atraso,
        para não gravar a cada pixel arrastado)."""
        if self._geom_job:
            self.after_cancel(self._geom_job)

        def gravar():
            self._geom_job = None
            try:
                if not self.winfo_exists():
                    return
                g = self.geometry()
            except Exception:  # noqa: BLE001
                return
            if "x" in g and self.state() == "normal":
                self.cfg[self._chave_geom()] = g
                settings.save(self.cfg)
        self._geom_job = self.after(800, gravar)

    def _geometria_valida(self, g: str) -> bool:
        """Descarta posições fora da tela (monitor desconectado, etc.)."""
        m = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", g or "")
        if not m:
            return False
        w, h, x, y = (int(v) for v in m.groups())
        if w < 200 or h < 160:
            return False
        larg, alt = self.winfo_screenwidth(), self.winfo_screenheight()
        # tolera monitores à esquerda/acima (coordenadas negativas)
        return -larg < x < larg * 2 and -alt < y < alt * 2

    def _apply_window_mode(self, initial=False):
        self.minsize(330, 480) if self.widget_mode else self.minsize(620, 430)
        salva = self.cfg.get(self._chave_geom(), "")
        if self.widget_mode and salva:
            # versões antigas guardaram uma janelinha curta demais para
            # mostrar o painel de andamento: cresce para baixo, no lugar
            m = re.match(r"(\d+)x(\d+)(\+-?\d+\+-?\d+)$", salva)
            if m and int(m.group(2)) < 520:
                salva = f"{max(int(m.group(1)), 380)}x580{m.group(3)}"
        if self._geometria_valida(salva):
            self.geometry(salva)
        else:
            self.geometry(WIDGET_SIZE if self.widget_mode else FULL_SIZE)
        top = bool(self.cfg.get("always_on_top", True)) and self.widget_mode
        self.attributes("-topmost", top)
        if not initial:
            self._show_main()

    def _toggle_mode(self):
        self._gravar_agora()
        self.widget_mode = not self.widget_mode
        self._apply_window_mode()

    def _gravar_agora(self):
        try:
            g = self.geometry()
            if "x" in g and self.state() == "normal":
                self.cfg[self._chave_geom()] = g
                settings.save(self.cfg)
        except Exception:  # noqa: BLE001
            pass

    def _ao_fechar(self):
        if self._geom_job:
            try:
                self.after_cancel(self._geom_job)
            except Exception:  # noqa: BLE001
                pass
            self._geom_job = None
        self._gravar_agora()
        # cancela callbacks pendentes (o rastreador de DPI do CustomTkinter
        # continua agendado e reclama depois que a janela some)
        try:
            for ident in self.tk.call("after", "info"):
                try:
                    self.after_cancel(ident)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            pass
        self.destroy()

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
            def ir_para_3():
                self._chave_digitada = self.key_entry.get().strip()
                self._show_onboarding(3)

            self.key_next = ctk.CTkButton(
                row, text="Continuar  →", height=40, state="disabled",
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                command=ir_para_3)
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
                self._chave_digitada = key
                self.after(0, lambda: (
                    self.key_status.configure(
                        text=f"✓ Chave válida!{saldo}", text_color=OK_COLOR),
                    self.key_next.configure(state="normal")))
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                try:
                    self.after(0, lambda: self.key_status.configure(
                        text=f"✗ {msg}", text_color=ERR_COLOR))
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=check, daemon=True).start()

    def _finish_onboarding(self):
        try:
            chave = getattr(self, "_chave_digitada", "") or self.cfg.get(
                "api_key", "")
            self.cfg["api_key"] = chave
            self.cfg["generate_pdf"] = self.pdf_var.get()
            self.cfg["always_on_top"] = bool(self.top_var.get())
            self.cfg["onboarded"] = True
            settings.save(self.cfg)
        except Exception as e:  # noqa: BLE001 — nunca falhar em silêncio
            from tkinter import messagebox
            messagebox.showerror(
                "Erro ao salvar", f"Não foi possível concluir: {e}")
            return
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

        if self.update_info:
            ctk.CTkButton(
                outer, height=30, fg_color="#B7791F", hover_color="#975A16",
                text=f"⬆  Atualizar para a versão {self.update_info['versao']}",
                command=self._atualizar_agora).pack(fill="x", pady=(6, 0))

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=(8, 0))

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        mem = memory.load()
        self.perfil_var = ctk.StringVar(value="Detectar automaticamente")
        ctk.CTkOptionMenu(left, values=list(mem["perfis"]),
                          variable=self.perfil_var, height=28,
                          dynamic_resizing=False).pack(fill="x", pady=(0, 6))

        # área de drop
        self.drop = ctk.CTkFrame(left, corner_radius=16, border_width=2,
                                 border_color=ACCENT,
                                 height=165 if self.widget_mode else 200)
        self.drop.pack(fill="x", expand=False)
        self.drop.pack_propagate(False)
        self.drop_label = ctk.CTkLabel(
            self.drop, justify="center",
            font=ctk.CTkFont(size=15, weight="bold"),
            text="📄\nSolte o relatório aqui\n(.docx ou .xlsx)")
        self.drop_label.place(relx=0.5, rely=0.40, anchor="center")
        ctk.CTkButton(self.drop, text="ou clique para escolher",
                      fg_color="transparent", text_color=ACCENT,
                      hover=False, command=self._pick_file).place(
            relx=0.5, rely=0.80, anchor="center")

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
        ctk.CTkLabel(left, text="Andamento", anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            fill="x", pady=(8, 2))
        self.log_box = ctk.CTkTextbox(
            left, height=110 if self.widget_mode else 150,
            font=ctk.CTkFont(size=11))
        self.log_box.pack(fill="both", expand=True)
        self.log_box.insert("1.0", "Solte um arquivo para começar.\n")
        self.log_box.configure(state="disabled")
        linha_cp = ctk.CTkFrame(left, fg_color="transparent")
        linha_cp.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(linha_cp, text="📋 Copiar resumo", height=26,
                      fg_color="gray50", command=self._copiar_resumo).pack(
            side="left", expand=True, fill="x", padx=(0, 3))
        ctk.CTkButton(linha_cp, text="🧹", height=26, width=40,
                      fg_color="gray50", command=self._limpar_log).pack(
            side="left")

        self.open_btn = ctk.CTkButton(left, text="📂  Abrir pasta",
                                      fg_color=OK_COLOR, height=34,
                                      command=lambda: None)
        self.redo_btn = ctk.CTkButton(
            left, text="🔁  Refazer com a instrução acima", height=30,
            fg_color="gray50", command=self._reprocess)

        # painel lateral (modo janela)
        if not self.widget_mode:
            right = ctk.CTkFrame(body, width=360)
            right.pack(side="right", fill="both", padx=(12, 0))
            tabs = ctk.CTkTabview(right, width=350)
            tabs.pack(fill="both", expand=True, padx=6, pady=6)
            self._build_forms_tab(tabs.add("Formulários"))
            self._build_search_tab(tabs.add("Busca"))
            self._build_history_tab(tabs.add("Histórico"))
            self._build_memory_tab(tabs.add("Memória"))
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

    # --------------------------------------------------- formulários

    def _build_forms_tab(self, tab):
        topo = ctk.CTkFrame(tab, fg_color="transparent")
        topo.pack(fill="x", pady=(2, 4))
        modelos = forms.listar() or ["(nenhum modelo ainda)"]
        self.modelo_var = ctk.StringVar(value=modelos[0])
        sel = ctk.CTkOptionMenu(topo, values=modelos, variable=self.modelo_var,
                                dynamic_resizing=False, width=200)
        sel.pack(side="left", fill="x", expand=True)

        campos_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent",
                                              height=200)
        campos_frame.pack(fill="both", expand=True)
        self.campos_widgets = {}
        status = ctk.CTkLabel(tab, text="", wraplength=310, text_color="gray",
                              font=ctk.CTkFont(size=11))

        def montar_campos(_=None):
            for w in campos_frame.winfo_children():
                w.destroy()
            self.campos_widgets.clear()
            nome = self.modelo_var.get()
            if not nome.endswith(".docx"):
                ctk.CTkLabel(campos_frame, wraplength=300, text_color="gray",
                             justify="left",
                             text=("Nenhum modelo importado ainda.\n\n"
                                   "Um modelo e um documento do servico "
                                   "(com timbre e assinatura) onde os lugares "
                                   "a preencher estao marcados assim:\n\n"
                                   "Usuario(a): {{nome}}\n"
                                   "Encaminhado para: {{destino}}\n\n"
                                   "Clique em Importar.")).pack(pady=10, padx=6)
                return
            try:
                lista = forms.campos(nome)
            except Exception as e:
                status.configure(text=f"x {e}", text_color=ERR_COLOR)
                return
            if not lista:
                ctk.CTkLabel(campos_frame, wraplength=300,
                             text_color=ERR_COLOR,
                             text="Este modelo nao tem marcadores.").pack(pady=10)
                return
            for c in lista:
                ctk.CTkLabel(campos_frame,
                             text=c.replace("_", " ").capitalize(), anchor="w",
                             font=ctk.CTkFont(size=11, weight="bold")).pack(
                    fill="x", pady=(6, 1))
                cx = ctk.CTkTextbox(campos_frame, height=46,
                                    font=ctk.CTkFont(size=11))
                cx.pack(fill="x")
                self.campos_widgets[c] = cx

        sel.configure(command=montar_campos)
        montar_campos()

        def importar():
            from tkinter import filedialog
            f = filedialog.askopenfilename(title="Escolha o modelo (.docx)",
                                           filetypes=[("Word", "*.docx")])
            if not f:
                return
            nome = forms.importar(f)
            sel.configure(values=forms.listar())
            self.modelo_var.set(nome)
            montar_campos()
            status.configure(text=f"Modelo {nome} importado.",
                             text_color=OK_COLOR)

        ctk.CTkButton(topo, text="Importar...", width=88, height=28,
                      fg_color="gray50", command=importar).pack(side="left",
                                                                padx=(6, 0))

        ctk.CTkLabel(tab, anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text="Ou cole anotacoes e deixe a IA distribuir:").pack(
            fill="x", pady=(8, 2))
        anotacoes = ctk.CTkTextbox(tab, height=66, font=ctk.CTkFont(size=11))
        anotacoes.pack(fill="x")

        def preencher_ia():
            texto = anotacoes.get("1.0", "end").strip()
            if not texto or not self.campos_widgets:
                status.configure(text="Escreva as anotacoes primeiro.",
                                 text_color=ERR_COLOR)
                return
            if not self.cfg.get("api_key"):
                status.configure(text="Configure a chave OpenRouter.",
                                 text_color=ERR_COLOR)
                return
            status.configure(text="Distribuindo nos campos...",
                             text_color="gray")

            def tarefa():
                try:
                    cli = ai_client.OpenRouterClient(self.cfg["api_key"],
                                                     model=self.cfg["model"])
                    vals = forms.distribuir_com_ia(
                        cli, list(self.campos_widgets), texto)

                    def aplicar():
                        for c, w in self.campos_widgets.items():
                            w.delete("1.0", "end")
                            w.insert("1.0", vals.get(c, ""))
                        status.configure(
                            text=f"Campos preenchidos - US$ "
                                 f"{cli.total_cost:.4f}. Confira antes de gerar.",
                            text_color=OK_COLOR)
                    self.after(0, aplicar)
                except Exception as e:
                    msg = str(e)
                    self.after(0, lambda: status.configure(
                        text=f"x {msg}", text_color=ERR_COLOR))
            threading.Thread(target=tarefa, daemon=True).start()

        linha = ctk.CTkFrame(tab, fg_color="transparent")
        linha.pack(fill="x", pady=6)
        ctk.CTkButton(linha, text="Preencher com IA", height=30,
                      fg_color="gray50", command=preencher_ia).pack(
            side="left", expand=True, fill="x", padx=(0, 4))

        def gerar():
            nome = self.modelo_var.get()
            if not nome.endswith(".docx") or not self.campos_widgets:
                return
            valores = {c: w.get("1.0", "end").strip()
                       for c, w in self.campos_widgets.items()}
            from tkinter import filedialog
            base = os.path.splitext(nome)[0]
            rotulo = valores.get("nome") or valores.get("usuario") or ""
            sugerido = (f"{base} - {rotulo}.docx" if rotulo
                        else f"{base} preenchido.docx")
            sugerido = "".join(ch for ch in sugerido if ch not in '\\/:*?"<>|')
            destino = filedialog.asksaveasfilename(
                title="Salvar formulario", defaultextension=".docx",
                initialfile=sugerido, filetypes=[("Word", "*.docx")])
            if not destino:
                return
            try:
                forms.preencher(nome, valores, destino)
                status.configure(text=f"Gerado: {os.path.basename(destino)}",
                                 text_color=OK_COLOR)
                open_folder(destino)
            except Exception as e:
                status.configure(text=f"x {e}", text_color=ERR_COLOR)

        ctk.CTkButton(linha, text="Gerar documento", height=30,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=gerar).pack(side="left", expand=True, fill="x")
        status.pack(fill="x")

    # --------------------------------------------------------- busca

    def _build_search_tab(self, tab):
        topo = ctk.CTkFrame(tab, fg_color="transparent")
        topo.pack(fill="x", pady=(4, 6))
        entry = ctk.CTkEntry(topo, placeholder_text="Buscar nos relatórios…")
        entry.pack(side="left", fill="x", expand=True)
        res_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        res_frame.pack(fill="both", expand=True)
        info = ctk.CTkLabel(tab, text_color="gray", font=ctk.CTkFont(size=11),
                            text=f"{archive.total()} documento(s) no índice")
        info.pack(fill="x")

        def mostrar(itens):
            for w in res_frame.winfo_children():
                w.destroy()
            if not itens:
                ctk.CTkLabel(res_frame, text="Nada encontrado.",
                             text_color="gray").pack(pady=16)
                return
            for it in itens:
                card = ctk.CTkFrame(res_frame, corner_radius=8)
                card.pack(fill="x", pady=3, padx=2)
                ctk.CTkLabel(card, text=it["nome"], anchor="w",
                             font=ctk.CTkFont(size=12, weight="bold")).pack(
                    fill="x", padx=8, pady=(5, 0))
                ctk.CTkLabel(card, text=it["trecho"][:150], anchor="w",
                             wraplength=300, justify="left",
                             text_color="gray").pack(fill="x", padx=8)
                ctk.CTkButton(card, text="Abrir pasta", height=24, width=90,
                              fg_color="gray50",
                              command=lambda c=it["caminho"]:
                              open_folder(c)).pack(anchor="e", padx=8, pady=4)

        def buscar(_evt=None):
            mostrar(archive.buscar(entry.get()))

        entry.bind("<Return>", buscar)
        ctk.CTkButton(topo, text="🔍", width=40,
                      command=buscar).pack(side="left", padx=(6, 0))

        def indexar_pasta():
            from tkinter import filedialog
            pasta = filedialog.askdirectory(
                title="Escolha a pasta com os relatórios")
            if not pasta:
                return
            info.configure(text="Indexando…")

            def tarefa():
                n = archive.indexar_pasta(
                    pasta, progresso=lambda m: self.after(
                        0, info.configure, {"text": m}))
                self.after(0, info.configure, {
                    "text": f"{archive.total()} documento(s) no índice "
                            f"(+{n} agora)"})
            threading.Thread(target=tarefa, daemon=True).start()

        ctk.CTkButton(tab, text="📁  Indexar uma pasta…", height=30,
                      fg_color="gray50", command=indexar_pasta).pack(
            fill="x", pady=(6, 0))

    # -------------------------------------------------------- memória

    def _build_memory_tab(self, tab):
        mem = memory.load()
        frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        frame.pack(fill="both", expand=True)

        ctk.CTkLabel(frame, anchor="w", wraplength=310, text_color="gray",
                     text="Textos oficiais do serviço. O app avisa quando um "
                          "relatório traz esses trechos com diferenças.").pack(
            fill="x", pady=(4, 6))

        nomes = list(mem["blocos"]) or ["Descrição do serviço"]
        bloco_var = ctk.StringVar(value=nomes[0])
        seletor = ctk.CTkOptionMenu(frame, values=nomes, variable=bloco_var,
                                    dynamic_resizing=False)
        seletor.pack(fill="x")
        nome_entry = ctk.CTkEntry(frame, placeholder_text="Nome do bloco")
        nome_entry.pack(fill="x", pady=(6, 4))
        nome_entry.insert(0, bloco_var.get())
        txt = ctk.CTkTextbox(frame, height=150)
        txt.pack(fill="x")
        txt.insert("1.0", mem["blocos"].get(bloco_var.get(), ""))

        def trocar(nome):
            nome_entry.delete(0, "end")
            nome_entry.insert(0, nome)
            txt.delete("1.0", "end")
            txt.insert("1.0", mem["blocos"].get(nome, ""))
        seletor.configure(command=trocar)

        aviso = ctk.CTkLabel(frame, text="", text_color=OK_COLOR)

        def salvar_bloco():
            nome = nome_entry.get().strip()
            corpo = txt.get("1.0", "end").strip()
            if not nome:
                return
            mem["blocos"][nome] = corpo
            memory.save(mem)
            seletor.configure(values=list(mem["blocos"]))
            bloco_var.set(nome)
            aviso.configure(text="✓ Bloco salvo")
            self.after(2000, lambda: aviso.configure(text=""))

        def apagar_bloco():
            mem["blocos"].pop(nome_entry.get().strip(), None)
            memory.save(mem)
            restantes = list(mem["blocos"]) or ["Descrição do serviço"]
            seletor.configure(values=restantes)
            bloco_var.set(restantes[0])
            trocar(restantes[0])

        linha = ctk.CTkFrame(frame, fg_color="transparent")
        linha.pack(fill="x", pady=6)
        ctk.CTkButton(linha, text="Salvar bloco", fg_color=ACCENT,
                      hover_color=ACCENT_HOVER,
                      command=salvar_bloco).pack(side="left", expand=True,
                                                 fill="x", padx=(0, 4))
        ctk.CTkButton(linha, text="Apagar", fg_color="gray50", width=80,
                      command=apagar_bloco).pack(side="left")
        aviso.pack()

        # ---- fatos institucionais ----
        ctk.CTkLabel(frame, anchor="w", text="Fatos institucionais",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            fill="x", pady=(14, 2))
        ctk.CTkLabel(frame, anchor="w", wraplength=310, text_color="gray",
                     font=ctk.CTkFont(size=11),
                     text=("Um por linha. Servem de contexto para a IA "
                           "entender o texto — ela nunca acrescenta essas "
                           "informações ao documento. Você também pode "
                           "escrever “lembrar: ...” no campo de instruções.")
                     ).pack(fill="x")
        fatos_box = ctk.CTkTextbox(frame, height=90)
        fatos_box.pack(fill="x", pady=(2, 0))
        fatos_box.insert("1.0", "\n".join(mem.get("fatos", [])))

        fav = ctk.CTkLabel(frame, text="", text_color=OK_COLOR)

        def salvar_fatos():
            mem["fatos"] = [l.strip() for l in
                            fatos_box.get("1.0", "end").splitlines() if l.strip()]
            memory.save(mem)
            fav.configure(text="✓ Fatos salvos")
            self.after(2000, lambda: fav.configure(text=""))

        ctk.CTkButton(frame, text="Salvar fatos", fg_color=ACCENT,
                      hover_color=ACCENT_HOVER, command=salvar_fatos).pack(
            fill="x", pady=6)
        fav.pack()

        # ---- perfis ----
        ctk.CTkLabel(frame, anchor="w", text="Perfis de documento",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            fill="x", pady=(14, 2))
        editaveis = [n for n in mem["perfis"] if n != "Detectar automaticamente"]
        perfil_var = ctk.StringVar(value=editaveis[0])
        psel = ctk.CTkOptionMenu(frame, values=editaveis, variable=perfil_var,
                                 dynamic_resizing=False)
        psel.pack(fill="x")
        ctk.CTkLabel(frame, anchor="w", text_color="gray",
                     text="Assinatura (uma linha por rótulo; vazio = manter "
                          "a do documento)").pack(fill="x", pady=(6, 2))
        assin = ctk.CTkTextbox(frame, height=60)
        assin.pack(fill="x")
        instr = ctk.CTkEntry(frame, placeholder_text="Instrução fixa (opcional)")
        instr.pack(fill="x", pady=(6, 0))

        def carregar_perfil(nome):
            p = mem["perfis"].get(nome, {})
            assin.delete("1.0", "end")
            assin.insert("1.0", "\n".join(p.get("assinatura", [])))
            instr.delete(0, "end")
            instr.insert(0, p.get("instrucoes", ""))
        carregar_perfil(perfil_var.get())
        psel.configure(command=carregar_perfil)

        pav = ctk.CTkLabel(frame, text="", text_color=OK_COLOR)

        def salvar_perfil():
            nome = perfil_var.get()
            p = mem["perfis"].setdefault(nome, {})
            p["assinatura"] = [l.strip() for l in
                               assin.get("1.0", "end").splitlines() if l.strip()]
            p["instrucoes"] = instr.get().strip()
            memory.save(mem)
            pav.configure(text="✓ Perfil salvo")
            self.after(2000, lambda: pav.configure(text=""))

        ctk.CTkButton(frame, text="Salvar perfil", fg_color=ACCENT,
                      hover_color=ACCENT_HOVER,
                      command=salvar_perfil).pack(fill="x", pady=6)
        pav.pack()

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
        rev = {v["id"]: k for k, v in ai_client.MODEL_CHOICES.items()}
        cur_id = self.cfg.get("model", ai_client.DEFAULT_MODEL)
        model_var = ctk.StringVar(
            value=rev.get(cur_id, next(iter(ai_client.MODEL_CHOICES))))
        custo_lbl = ctk.CTkLabel(frame, anchor="w", text_color="gray",
                                 font=ctk.CTkFont(size=11), text="")

        def _mostrar_custo(rotulo=None):
            r = rotulo or model_var.get()
            custo_lbl.configure(
                text=ai_client.MODEL_CHOICES.get(r, {}).get("custo", ""))

        ctk.CTkOptionMenu(frame, values=list(ai_client.MODEL_CHOICES),
                          variable=model_var, dynamic_resizing=False,
                          width=320, command=_mostrar_custo).pack(fill="x")
        custo_lbl.pack(fill="x")
        _mostrar_custo()

        field("Termos protegidos (a IA nunca corrige) — um por linha")
        terms = ctk.CTkTextbox(frame, height=110)
        terms.pack(fill="x")
        terms.insert("1.0", "\n".join(self.cfg.get("protected_terms", [])))

        field("Onde salvar os arquivos gerados")
        modo_var = ctk.StringVar(value=self.cfg.get("out_mode", "mesma"))
        ctk.CTkSegmentedButton(
            frame, values=["mesma", "fixa", "perguntar"],
            variable=modo_var).pack(fill="x")
        pasta_lbl = ctk.CTkLabel(
            frame, anchor="w", text_color="gray", font=ctk.CTkFont(size=11),
            text=self.cfg.get("out_dir") or "(mesma pasta do arquivo original)")
        pasta_lbl.pack(fill="x")
        escolhida = {"path": self.cfg.get("out_dir", "")}

        def escolher_pasta():
            from tkinter import filedialog
            d = filedialog.askdirectory(title="Pasta fixa de saída")
            if d:
                escolhida["path"] = d
                pasta_lbl.configure(text=d)
                modo_var.set("fixa")

        ctk.CTkButton(frame, text="Escolher pasta fixa…", height=28,
                      fg_color="gray50", command=escolher_pasta).pack(
            fill="x", pady=(4, 0))
        ctk.CTkLabel(frame, anchor="w", text_color="gray", wraplength=310,
                     font=ctk.CTkFont(size=11),
                     text=("Dica: você também pode escrever no campo de "
                           "instruções “salvar na área de trabalho” ou "
                           "“salvar na pasta Relatórios” — vale só para "
                           "aquele arquivo.")).pack(fill="x", pady=(2, 0))

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

        upd_var = ctk.BooleanVar(value=self.cfg.get("check_updates", True))
        ctk.CTkCheckBox(frame, text="Avisar quando houver nova versão",
                        variable=upd_var).pack(anchor="w", pady=(10, 4))
        ctk.CTkButton(frame, text="Procurar atualização agora", height=28,
                      fg_color="gray50",
                      command=lambda: self._checar_atualizacao(True)).pack(
            fill="x")
        ctk.CTkLabel(frame, anchor="w", text_color="gray",
                     font=ctk.CTkFont(size=11),
                     text=f"Versão instalada: {version.VERSION}").pack(
            fill="x", pady=(2, 0))

        def save_all():
            lista = [t.strip() for t in terms.get("1.0", "end").splitlines()
                     if t.strip()]
            self.cfg.update(api_key=key.get().strip(),
                            model=ai_client.model_id(model_var.get()),
                            generate_pdf=pdf.get(),
                            always_on_top=bool(top_var.get()),
                            theme=theme_var.get(),
                            protected_terms=lista,
                            out_mode=modo_var.get(),
                            out_dir=escolhida["path"],
                            check_updates=bool(upd_var.get()))
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
        paths = filedialog.askopenfilenames(
            title="Escolha um ou mais documentos",
            filetypes=[("Documentos", "*.docx *.xlsx")])
        if paths:
            self._enqueue(list(paths))

    def _on_drop(self, event):
        try:
            paths = list(self.tk.splitlist(event.data))
        except Exception:  # noqa: BLE001
            raw = event.data.strip()
            paths = [raw[1:-1] if raw.startswith("{") else raw]
        self._enqueue(paths)

    # ------------------------------------------------------------ fila

    def _enqueue(self, paths: list[str]):
        validos = [p for p in paths if os.path.isfile(p)
                   and os.path.splitext(p)[1].lower() in (".docx", ".xlsx")]
        if not validos:
            self._set_status("Solte arquivos .docx ou .xlsx.", ERR_COLOR)
            return
        self.queue.extend(validos)
        if not self.busy:
            self._next_in_queue()

    def _next_in_queue(self):
        if not self.queue:
            return
        path = self.queue.pop(0)
        self._start(path)

    def _ask_pdf(self) -> bool:
        pref = self.cfg.get("generate_pdf", "perguntar")
        if pref == "sempre":
            return True
        if pref == "nunca":
            return False
        from tkinter import messagebox
        return bool(messagebox.askyesno(
            "PDF", "Gerar também um PDF da versão final?"))

    def _start(self, path: str):
        if self.busy:
            return
        if not self.cfg.get("api_key"):
            self._set_status("Configure a chave OpenRouter primeiro "
                             "(modo janela → Configurações).", ERR_COLOR)
            return
        self.last_path = path
        want_pdf = (os.path.splitext(path)[1].lower() == ".docx"
                    and self._ask_pdf())

        def perguntar_pasta():
            from tkinter import filedialog
            return filedialog.askdirectory(
                title="Onde salvar os arquivos gerados?")

        pasta, instrucoes = outdir.resolver(
            self.cfg, path, perguntar_fn=perguntar_pasta,
            instrucoes=self.extra_entry.get().strip())
        self.busy = True
        self.open_btn.pack_forget()
        self.redo_btn.pack_forget()
        restantes = f"  (+{len(self.queue)} na fila)" if self.queue else ""
        self.drop_label.configure(
            text=f"⏳ Processando…{restantes}\n{os.path.basename(path)[:30]}")
        self.progress.pack(fill="x", pady=(4, 2))
        self.progress.start()
        destino = os.path.basename(pasta) if pasta else "mesma pasta do arquivo"
        self._set_status(f"Iniciando… (salvando em: {destino})", "gray")

        job = worker.Job(
            path, self.cfg, instrucoes,
            on_progress=lambda m: self.after(0, self._set_status, m, "gray"),
            on_done=lambda r: self.after(0, self._done, r),
            on_error=lambda e: self.after(0, self._fail, e),
            want_pdf=want_pdf, perfil=self.perfil_var.get(), out_dir=pasta)
        job.start()

    def _reprocess(self):
        """Refaz o último arquivo com a instrução atual do campo."""
        if self.last_path and not self.busy:
            self._start(self.last_path)

    def _set_status(self, msg: str, color: str = "gray"):
        self.status.configure(text=msg, text_color=color)
        self._log(msg)

    def _log(self, msg: str):
        box = getattr(self, "log_box", None)
        if not box:
            self.log_linhas = getattr(self, "log_linhas", [])
            self.log_linhas.append(msg)
            return
        box.configure(state="normal")
        box.insert("end", msg + "\n")
        box.see("end")
        box.configure(state="disabled")

    def _texto_log(self) -> str:
        box = getattr(self, "log_box", None)
        if box:
            return box.get("1.0", "end").strip()
        return "\n".join(getattr(self, "log_linhas", []))

    def _copiar_resumo(self):
        self.clipboard_clear()
        self.clipboard_append(self._texto_log())
        self._log("(resumo copiado para a área de transferência)")

    def _limpar_log(self):
        box = getattr(self, "log_box", None)
        if box:
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.configure(state="disabled")
        self.log_linhas = []

    def _done(self, res: dict):
        self.busy = False
        self.progress.stop()
        self.progress.pack_forget()
        self.drop_label.configure(
            text="✅\nPronto! Solte outro arquivo")
        extra = f"  ·  US$ {res['cost']:.3f}" if res.get("cost") else ""
        warn = f"\n⚠ {len(res['warnings'])} aviso(s)" \
            if res.get("warnings") else ""
        self.status.configure(
            text=f"✓ {res['changed']} correções em {res['paragraphs']} "
                 f"parágrafos{extra}{warn}",
            text_color=OK_COLOR if res.get("verified") else ERR_COLOR)

        # resumo completo no painel
        self._log("")
        self._log("═══ RESUMO ═══")
        if res.get("perfil"):
            self._log(f"Perfil aplicado: {res['perfil']}")
        self._log(f"Parágrafos: {res['paragraphs']}  |  corrigidos: "
                  f"{res['changed']}")
        if res.get("cost"):
            self._log(f"Custo desta revisão: US$ {res['cost']:.4f}")
        self._log(f"Conferência final: "
                  f"{'OK' if res.get('verified') else 'ATENÇÃO — revise o diff'}")
        for w in res.get("warnings") or []:
            self._log(f"  • {w}")
        self._log("Arquivos gerados:")
        self._log(f"  {os.path.basename(res['final'])}")
        self._log(f"  {os.path.basename(res['redline'])}")
        if res.get("pdf"):
            self._log(f"  {os.path.basename(res['pdf'])}")
        self._log(f"Pasta: {os.path.dirname(res['final'])}")
        self.open_btn.configure(command=lambda: open_folder(res["final"]))
        self.open_btn.pack(fill="x", pady=(4, 0))
        self.redo_btn.pack(fill="x", pady=(4, 0))
        if self.queue:
            self.after(600, self._next_in_queue)

    def _fail(self, err: str):
        self.busy = False
        self.progress.stop()
        self.progress.pack_forget()
        self.drop_label.configure(
            text="📄\nSolte o relatório aqui\n(.docx ou .xlsx)")
        self._set_status(f"✗ {err}", ERR_COLOR)
        if self.queue:
            self.after(1200, self._next_in_queue)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
