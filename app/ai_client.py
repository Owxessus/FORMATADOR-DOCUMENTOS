# -*- coding: utf-8 -*-
"""Cliente OpenRouter para correção de texto (ortografia/coerência)."""
from __future__ import annotations

import json
import re

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_URL = "https://openrouter.ai/api/v1/key"
DEFAULT_MODEL = "google/gemini-3.7-flash"

# Opções oferecidas no menu de configurações (rótulo → id na OpenRouter).
MODEL_CHOICES = {
    "Gemini 3.7 Flash — rápido e econômico (padrão)": "google/gemini-3.7-flash",
    "Gemini 3.6 Flash — alternativa": "google/gemini-3.6-flash",
    "Claude Sonnet 4.5 — mais caro, texto mais refinado":
        "anthropic/claude-sonnet-4.5",
    "GPT-5 mini — alternativa": "openai/gpt-5-mini",
}

SYSTEM_PROMPT = """Você é um revisor profissional de documentos institucionais \
brasileiros (relatórios de assistência social, ocorrências, respostas a órgãos \
públicos). Sua ÚNICA tarefa é corrigir ortografia, gramática, pontuação, \
acentuação e coerência de frases, mantendo tom formal.

REGRAS INVIOLÁVEIS:
1. NUNCA altere fatos, datas, horários, nomes de pessoas ou lugares, números, \
valores, siglas, códigos (CID, CRM, RG, protocolos, placas) ou o sentido do texto.
2. NUNCA acrescente informações novas nem remova informações existentes.
3. NUNCA mude a ordem dos parágrafos. Cada parágrafo de entrada corresponde a \
exatamente um parágrafo de saída, na mesma posição.
4. Pode reorganizar frases muito longas dentro do MESMO parágrafo para dar \
clareza, sem mudar o conteúdo.
5. Se um parágrafo já estiver correto, devolva-o exatamente igual.
6. Padronize horários no formato 07h00 e mantenha datas como estão.
7. NUNCA altere siglas, nomes próprios, nomes de medicamentos, unidades de saúde, bairros ou termos técnicos — mesmo que pareçam grafados de forma estranha. Na dúvida, deixe como está.

FORMATO: você receberá JSON {"paragrafos": [{"i": 0, "texto": "..."}, ...]} e \
deve responder APENAS com JSON válido no mesmo formato, mesmos índices, mesma \
quantidade."""


class ApiError(Exception):
    pass


class OpenRouterClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL,
                 timeout: int = 180):
        self.api_key = api_key.strip()
        self.model = model
        self.timeout = timeout
        self.total_cost = 0.0  # USD (créditos OpenRouter)

    # ------------------------------------------------------------ chave

    def validate_key(self) -> dict:
        """Valida a chave; retorna dados de uso/limite da conta."""
        r = requests.get(KEY_URL, timeout=30,
                         headers={"Authorization": f"Bearer {self.api_key}"})
        if r.status_code == 401:
            raise ApiError("Chave inválida. Confira se copiou a chave inteira.")
        r.raise_for_status()
        return r.json().get("data", {})

    # --------------------------------------------------------- correção

    def _chat(self, payload_msgs: list[dict]) -> str:
        body = {
            "model": self.model,
            "messages": payload_msgs,
            "temperature": 0.2,
            "usage": {"include": True},
        }
        r = requests.post(
            API_URL, json=body, timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/formatador-relatorios",
                "X-Title": "Formatador de Relatorios",
            })
        if r.status_code == 401:
            raise ApiError("Chave inválida ou expirada.")
        if r.status_code == 402:
            raise ApiError("Créditos insuficientes na conta OpenRouter.")
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise ApiError(str(data["error"].get("message", data["error"])))
        usage = data.get("usage") or {}
        self.total_cost += float(usage.get("cost") or 0.0)
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_json(content: str) -> list[dict]:
        m = re.search(r"\{.*\}", content, flags=re.S)
        if not m:
            raise ApiError("Resposta da IA sem JSON.")
        return json.loads(m.group(0))["paragrafos"]

    def _correct_batch(self, batch: list[tuple[int, str]],
                       extra: str,
                       protected: list[str] | None = None) -> dict[int, str]:
        user = {"paragrafos": [{"i": i, "texto": t} for i, t in batch]}
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        if protected:
            msgs.append({"role": "system", "content":
                         "Termos que devem permanecer EXATAMENTE como estão "
                         "(nunca corrigir, acentuar ou expandir): "
                         + ", ".join(protected)})
        if extra.strip():
            msgs.append({"role": "system",
                         "content": "Instruções adicionais do usuário "
                                    f"(respeitando as regras invioláveis): {extra}"})
        msgs.append({"role": "user",
                     "content": json.dumps(user, ensure_ascii=False)})

        last_err = None
        for attempt in range(3):
            try:
                items = self._parse_json(self._chat(msgs))
                out = {int(it["i"]): str(it["texto"]) for it in items}
                if set(out) == {i for i, _ in batch}:
                    return out
                last_err = ApiError("Índices divergentes na resposta.")
            except (ApiError, json.JSONDecodeError, KeyError, TypeError) as e:
                last_err = e
            msgs.append({"role": "user", "content":
                         "Sua resposta anterior estava fora do formato. "
                         "Responda SOMENTE o JSON pedido, com os mesmos índices."})
        raise ApiError(f"Falha na correção após 3 tentativas: {last_err}")

    def corrector(self, texts: list[str], kinds: list[str],
                  extra_instructions: str = "",
                  progress=lambda msg: None,
                  protected: list[str] | None = None) -> list[str]:
        """Assinatura compatível com docx_engine.process()."""
        indexed = list(enumerate(texts))
        batches, cur, size = [], [], 0
        for i, t in indexed:
            cur.append((i, t))
            size += len(t)
            if len(cur) >= 20 or size > 7000:
                batches.append(cur)
                cur, size = [], 0
        if cur:
            batches.append(cur)

        result: dict[int, str] = {}
        for n, b in enumerate(batches, 1):
            progress(f"Corrigindo texto com IA… (parte {n}/{len(batches)})")
            result.update(self._correct_batch(b, extra_instructions, protected))
        return [result[i] for i in range(len(texts))]
