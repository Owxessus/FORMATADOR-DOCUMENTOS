"""Onboarding completo, clicando nos botões como a usuária.

Regressão coberta: até a v1.5.1 o botão “Concluir” não fazia nada, porque
lia o campo da chave que já havia sido destruído ao trocar de passo — e a
exceção morria silenciosamente no callback do Tk.

Uso:  xvfb-run python3 tests/test_onboarding.py
""" 
import sys, time
sys.path.insert(0, __import__("os").path.join(
    __import__("os").path.dirname(__file__), "..", "app"))
import settings, main, ai_client, customtkinter as ctk

settings.save(settings.DEFAULTS.copy())
ai_client.OpenRouterClient.validate_key = lambda self: {"usage": 0.3, "limit": 5.0}

app = main.App()
res = {}

def botao(txt):
    achados = []
    def anda(w):
        for c in w.winfo_children():
            if isinstance(c, ctk.CTkButton) and txt in c.cget("text"):
                achados.append(c)
            anda(c)
    anda(app.container)
    return achados[0] if achados else None

def passo1():
    botao("Começar").invoke()
    app.after(200, passo2)

def passo2():
    app.key_entry.insert(0, "sk-or-v1-CHAVE-DE-TESTE")
    botao("Testar conexão").invoke()
    app.after(1200, passo3)

def passo3():
    res["status"] = app.key_status.cget("text")
    res["botao"] = app.key_next.cget("state")
    app.key_next.invoke()
    app.after(200, passo4)

def passo4():
    res["passo3_ok"] = hasattr(app, "pdf_var")
    botao("Concluir").invoke()
    app.after(300, fim)

def fim():
    salvo = settings.load()
    res["onboarded"] = salvo["onboarded"]
    res["chave"] = salvo["api_key"]
    res["widget"] = app.widget_mode
    res["drop"] = hasattr(app, "drop")
    app.quit()

app.after(300, passo1)
app.mainloop()
for k, v in res.items(): print(f"{k}: {v}")
assert res.get("onboarded") and res.get("chave") == "sk-or-v1-CHAVE-DE-TESTE" and res.get("drop")
print("ONBOARDING COMPLETO OK ✓")
