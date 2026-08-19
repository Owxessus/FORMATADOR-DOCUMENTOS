# -*- coding: utf-8 -*-
"""Controle de completude da revisão.

Um modelo de linguagem às vezes devolve um parágrafo intacto no meio de um
lote grande — não por estar correto, mas por "preguiça". Este módulo existe
para que isso não passe despercebido:

  1. procura pendências ÓBVIAS por código (sem IA) nos parágrafos que
     voltaram sem nenhuma alteração;
  2. entrega uma porcentagem de completude e a lista do que ficou de fora,
     com o motivo de cada caso;
  3. alimenta a segunda passada, que reenvia à IA só os parágrafos
     suspeitos — barato, porque são poucos.
"""
from __future__ import annotations

import re

# acentos que faltam com frequência e não têm forma alternativa válida
SEM_ACENTO = {
    "nao": "não", "voce": "você", "tambem": "também", "familia": "família",
    "familias": "famílias", "servico": "serviço", "servicos": "serviços",
    "saude": "saúde", "situacao": "situação", "situacoes": "situações",
    "informacao": "informação", "informacoes": "informações",
    "orientacao": "orientação", "orientacoes": "orientações",
    "medico": "médico", "medica": "médica", "publico": "público",
    "publica": "pública", "necessario": "necessário",
    "necessaria": "necessária", "possivel": "possível", "atraves": "através",
    "apos": "após", "mae": "mãe", "irma": "irmã", "ninguem": "ninguém",
    "alguem": "alguém", "porem": "porém", "tres": "três",
    "dificil": "difícil", "ultimo": "último", "ultima": "última",
    "proximo": "próximo", "proxima": "próxima", "periodo": "período",
    "horario": "horário", "relatorio": "relatório", "usuario": "usuário",
    "usuaria": "usuária", "tecnica": "técnica", "tecnico": "técnico",
    "psicologico": "psicológico", "psicologica": "psicológica",
    "fisica": "física", "quimica": "química", "convivio": "convívio",
    "domicilio": "domicílio", "responsavel": "responsável",
    "disponivel": "disponível", "referencia": "referência",
    "experiencia": "experiência", "violencia": "violência",
    "ocorrencia": "ocorrência", "residencia": "residência",
    "consciencia": "consciência", "adolescencia": "adolescência",
    "cabeca": "cabeça", "criancas": "crianças", "crianca": "criança",
    "obito": "óbito", "unico": "único", "unica": "única",
    "veiculo": "veículo", "juridico": "jurídico", "juridica": "jurídica",
    "assistencia": "assistência", "emergencia": "emergência",
}

_PALAVRA = re.compile(r"\b[a-zà-ÿ]+\b", re.I)


def pendencias(texto: str) -> list[str]:
    """Problemas visíveis por código. Lista vazia = nada evidente."""
    achados = []
    t = texto.strip()
    if not t:
        return achados

    faltando = sorted({
        p.lower() for p in _PALAVRA.findall(t)
        if p.lower() in SEM_ACENTO})
    if faltando:
        achados.append("acentuação: " + ", ".join(
            f"{p}→{SEM_ACENTO[p]}" for p in faltando[:4]))

    if re.search(r"[a-zà-ÿ]{2}  +[a-zà-ÿ]", t, re.I):
        achados.append("espaços duplicados")
    if re.search(r"\s+[,;.!?]", t):
        achados.append("espaço antes de pontuação")
    if re.search(r"[a-zà-ÿ],[a-zà-ÿ]", t, re.I):
        achados.append("falta espaço depois da vírgula")
    if re.search(r"\.\s+[a-zà-ÿ]", t):
        achados.append("minúscula depois de ponto final")
    if re.search(r"\b(\w{3,})\s+\1\b", t, re.I):
        achados.append("palavra repetida")
    if len(t) > 60 and t[-1] not in ".;:!?…\"”)":
        achados.append("sem pontuação final")
    if re.search(r"\d{1,2}:\d{2}\s*horas", t, re.I):
        achados.append("horário fora do padrão (07h00)")
    return achados


def analisar(paragrafos) -> dict:
    """Relatório de completude a partir dos parágrafos já processados.

    Cada item precisa ter: .kind, .text, .corrected e (opcional) .motivo.
    """
    total = len(paragrafos)
    corrigidos = citacoes = intactos = 0
    suspeitos = []
    for i, p in enumerate(paragrafos):
        if p.kind == "quote":
            citacoes += 1
            continue
        corr = p.corrected if p.corrected is not None else p.text
        if corr != p.text:
            corrigidos += 1
            continue
        intactos += 1
        pend = pendencias(p.text)
        if pend:
            suspeitos.append({
                "indice": i,
                "trecho": p.text[:70],
                "motivo": getattr(p, "motivo", "") or "devolvido sem alteração",
                "pendencias": pend,
            })
    revisaveis = max(total - citacoes, 1)
    completude = 100.0 * (revisaveis - len(suspeitos)) / revisaveis
    return {
        "total": total, "corrigidos": corrigidos, "citacoes": citacoes,
        "intactos": intactos, "suspeitos": suspeitos,
        "completude": round(completude, 1),
    }


def resumo_texto(rel: dict) -> list[str]:
    """Linhas prontas para o painel de andamento."""
    linhas = [f"Completude da revisão: {rel['completude']:.0f}%",
              f"  corrigidos: {rel['corrigidos']}  ·  sem alteração: "
              f"{rel['intactos']}  ·  citações preservadas: {rel['citacoes']}"]
    if rel["suspeitos"]:
        linhas.append(f"  ⚠ {len(rel['suspeitos'])} parágrafo(s) sem alteração "
                      f"com pendência aparente:")
        for s in rel["suspeitos"][:8]:
            linhas.append(f"     §{s['indice'] + 1} “{s['trecho']}…”")
            linhas.append(f"        pendência: {'; '.join(s['pendencias'])}")
            if s.get("motivo") and s["motivo"] != "devolvido sem alteração":
                linhas.append(f"        motivo: {s['motivo']}")
        if len(rel["suspeitos"]) > 8:
            linhas.append(f"     … e mais {len(rel['suspeitos']) - 8}")
        linhas.append("     (procure por “§” no diff ou revise esses "
                      "trechos à mão)")
    else:
        linhas.append("  nenhum parágrafo suspeito ficou sem revisão")
    linhas.append("  obs.: a checagem encontra erros evidentes (acentuação, "
                  "pontuação, repetição); não substitui a sua leitura.")
    return linhas
