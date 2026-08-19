# -*- coding: utf-8 -*-
"""Formulários: preencher modelos .docx com campos marcados.

Um modelo é um documento normal do serviço (com timbre, assinatura, tudo)
onde os lugares a preencher estão marcados assim:  {{nome}}, {{data}},
{{encaminhamento}}.

Fluxo na aba Formulários:
  1. a usuária escolhe o modelo;
  2. o app monta um campo para cada marcador;
  3. ela pode digitar campo a campo OU colar suas anotações soltas e
     pedir que a IA distribua a informação nos campos certos;
  4. o app gera o documento preenchido, preservando toda a formatação.

Os modelos ficam em <pasta de configuração>/modelos/.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import zipfile
from xml.sax.saxutils import escape

import settings

CAMPO_RE = re.compile(r"\{\{\s*([^}]{1,60}?)\s*\}\}")


def pasta_modelos() -> str:
    d = os.path.join(settings._config_dir(), "modelos")
    os.makedirs(d, exist_ok=True)
    return d


def listar() -> list[str]:
    return sorted(f for f in os.listdir(pasta_modelos())
                  if f.lower().endswith(".docx")
                  and not f.startswith("~$"))


def importar(caminho: str) -> str:
    destino = os.path.join(pasta_modelos(), os.path.basename(caminho))
    shutil.copy2(caminho, destino)
    return os.path.basename(destino)


# ------------------------------------------------------------- leitura

def _doc_xml(caminho: str) -> str:
    with zipfile.ZipFile(caminho) as z:
        return z.read("word/document.xml").decode("utf-8")


def _juntar_runs(xml: str) -> str:
    """Funde runs vizinhos de mesmo formato para que um marcador quebrado
    em vários pedaços ({{ no + me }}) volte a ser um texto contínuo."""
    def por_paragrafo(m):
        p = m.group(0)
        textos = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", p, flags=re.S)
        inteiro = "".join(textos)
        if "{{" not in inteiro or CAMPO_RE.search(inteiro) is None:
            return p
        # mantém o primeiro run e joga o texto todo nele
        runs = re.findall(r"<w:r\b(?:(?!</w:r>).)*</w:r>", p, flags=re.S)
        com_texto = [r for r in runs if "<w:t" in r]
        if not com_texto:
            return p
        primeiro = com_texto[0]
        novo = re.sub(r"(<w:t(?:\s[^>]*)?>).*?(</w:t>)",
                      lambda mm: mm.group(1) + inteiro + mm.group(2),
                      primeiro, count=1, flags=re.S)
        saida = p
        for i, r in enumerate(com_texto):
            saida = saida.replace(r, novo if i == 0 else "", 1)
        return saida
    return re.sub(r"<w:p\b(?:(?!</w:p>).)*</w:p>", por_paragrafo, xml,
                  flags=re.S)


def campos(nome_modelo: str) -> list[str]:
    """Marcadores do modelo, na ordem em que aparecem, sem repetição."""
    xml = _juntar_runs(_doc_xml(os.path.join(pasta_modelos(), nome_modelo)))
    vistos, saida = set(), []
    for m in CAMPO_RE.finditer(xml):
        c = m.group(1).strip()
        if c.lower() not in vistos:
            vistos.add(c.lower())
            saida.append(c)
    return saida


# ---------------------------------------------------------- preenchimento

def preencher(nome_modelo: str, valores: dict[str, str],
              destino: str) -> str:
    """Gera o documento preenchido; devolve o caminho."""
    origem = os.path.join(pasta_modelos(), nome_modelo)
    with zipfile.ZipFile(origem) as z:
        arquivos = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}

    xml = _juntar_runs(arquivos["word/document.xml"].decode("utf-8"))
    minusculo = {k.lower().strip(): v for k, v in valores.items()}

    def troca(m):
        chave = m.group(1).strip().lower()
        valor = minusculo.get(chave, "")
        # quebras de linha viram parágrafos dentro do mesmo run
        partes = escape(valor).split("\n")
        return "</w:t><w:br/><w:t xml:space=\"preserve\">".join(partes)

    xml = CAMPO_RE.sub(troca, xml)
    arquivos["word/document.xml"] = xml.encode("utf-8")

    os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        if "[Content_Types].xml" in arquivos:
            z.writestr("[Content_Types].xml", arquivos["[Content_Types].xml"])
        for n, d in arquivos.items():
            if n != "[Content_Types].xml":
                z.writestr(n, d)
    return destino


# ------------------------------------------------- preenchimento com IA

PROMPT = """Você organiza informações em formulários institucionais de \
assistência social. Receberá uma lista de campos e um texto com anotações \
soltas. Distribua as informações nos campos certos.

REGRAS:
1. Use SOMENTE informações presentes nas anotações. Nunca invente nada.
2. Campo sem informação correspondente fica com string vazia.
3. Não resuma a ponto de perder dados (datas, nomes, números, protocolos).
4. Corrija apenas ortografia e pontuação ao transcrever.
5. Responda APENAS com JSON: {"campos": {"nome_do_campo": "valor", ...}}"""


def distribuir_com_ia(client, lista_campos: list[str], anotacoes: str,
                      progresso=lambda m: None) -> dict[str, str]:
    """Pede à IA que encaixe as anotações nos campos do formulário."""
    pedido = {"campos": lista_campos, "anotacoes": anotacoes}
    msgs = [{"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(pedido, ensure_ascii=False)}]
    progresso("Distribuindo as informações nos campos…")
    resposta = client._chat(msgs)
    m = re.search(r"\{.*\}", resposta, flags=re.S)
    if not m:
        raise ValueError("A IA não devolveu JSON.")
    dados = json.loads(m.group(0)).get("campos", {})
    return {c: str(dados.get(c, "")) for c in lista_campos}
