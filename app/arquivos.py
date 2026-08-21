# -*- coding: utf-8 -*-
"""Conversões e operações com arquivos.

Ponto importante sobre PDF: ele guarda glifos posicionados, não parágrafos.
Por isso as operações se dividem em duas famílias:

  * MEXER NO PDF sem converter — juntar, dividir, extrair páginas, girar,
    proteger com senha, extrair texto e transformar páginas em imagem.
    Tudo isso é seguro e preserva o arquivo como está;

  * EDITAR O CONTEÚDO — aí é preciso converter para .docx, editar e, se for
    o caso, gerar PDF de novo. A conversão recupera o texto, não o layout,
    e isso é dito à usuária em vez de fingir que ficou igual.
"""
from __future__ import annotations

import os
import re
import zipfile
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter


def _saida(caminho: str, sufixo: str, ext: str | None = None,
           destino: str | None = None) -> str:
    if destino:
        return destino
    base, e = os.path.splitext(caminho)
    return f"{base}{sufixo}{ext or e}"


def paginas_de(spec: str, total: int) -> list[int]:
    """"1-3,7,10-" → [0,1,2,6,9,...] (índices base zero)."""
    if not spec or spec.strip().lower() in ("todas", "tudo", "all"):
        return list(range(total))
    saida = []
    for parte in re.split(r"[,;]", spec):
        parte = parte.strip()
        if not parte:
            continue
        if "-" in parte:
            a, _, b = parte.partition("-")
            ini = int(a) if a.strip() else 1
            fim = int(b) if b.strip() else total
        else:
            ini = fim = int(parte)
        saida.extend(range(max(ini, 1) - 1, min(fim, total)))
    return sorted(set(saida))


# ------------------------------------------------- PDF sem converter

def pdf_juntar(caminhos: list[str], destino: str) -> str:
    w = PdfWriter()
    for c in caminhos:
        for pag in PdfReader(c).pages:
            w.add_page(pag)
    with open(destino, "wb") as f:
        w.write(f)
    return destino


def pdf_dividir(caminho: str, pasta: str | None = None) -> list[str]:
    r = PdfReader(caminho)
    pasta = pasta or os.path.dirname(os.path.abspath(caminho))
    base = os.path.splitext(os.path.basename(caminho))[0]
    saidas = []
    for i, pag in enumerate(r.pages, 1):
        w = PdfWriter()
        w.add_page(pag)
        destino = os.path.join(pasta, f"{base}_pag{i:02d}.pdf")
        with open(destino, "wb") as f:
            w.write(f)
        saidas.append(destino)
    return saidas


def pdf_extrair_paginas(caminho: str, spec: str,
                        destino: str | None = None) -> str:
    r = PdfReader(caminho)
    w = PdfWriter()
    for i in paginas_de(spec, len(r.pages)):
        w.add_page(r.pages[i])
    destino = _saida(caminho, "_paginas", destino=destino)
    with open(destino, "wb") as f:
        w.write(f)
    return destino


def pdf_girar(caminho: str, graus: int = 90, spec: str = "",
              destino: str | None = None) -> str:
    r = PdfReader(caminho)
    alvo = set(paginas_de(spec, len(r.pages)))
    w = PdfWriter()
    for i, pag in enumerate(r.pages):
        if i in alvo:
            pag.rotate(int(graus))
        w.add_page(pag)
    destino = _saida(caminho, "_girado", destino=destino)
    with open(destino, "wb") as f:
        w.write(f)
    return destino


def pdf_proteger(caminho: str, senha: str,
                 destino: str | None = None) -> str:
    r = PdfReader(caminho)
    w = PdfWriter()
    for pag in r.pages:
        w.add_page(pag)
    w.encrypt(senha)
    destino = _saida(caminho, "_protegido", destino=destino)
    with open(destino, "wb") as f:
        w.write(f)
    return destino


def pdf_texto(caminho: str) -> str:
    r = PdfReader(caminho)
    return "\n\n".join((p.extract_text() or "").strip() for p in r.pages)


def pdf_tem_texto(caminho: str) -> bool:
    """False = PDF digitalizado (só imagem); precisa de OCR."""
    return len(pdf_texto(caminho).strip()) > 40


def pdf_para_imagens(caminho: str, pasta: str | None = None,
                     dpi: int = 150, limite: int = 20) -> list[str]:
    """Páginas viram PNG — é assim que um PDF digitalizado vai para o OCR."""
    import pypdfium2 as pdfium
    pasta = pasta or os.path.dirname(os.path.abspath(caminho))
    base = os.path.splitext(os.path.basename(caminho))[0]
    doc = pdfium.PdfDocument(caminho)
    saidas = []
    for i in range(min(len(doc), limite)):
        img = doc[i].render(scale=dpi / 72).to_pil()
        destino = os.path.join(pasta, f"{base}_pag{i + 1:02d}.png")
        img.save(destino)
        saidas.append(destino)
    return saidas


def imagens_para_pdf(caminhos: list[str], destino: str) -> str:
    """Fotos de documentos viram um PDF único."""
    from PIL import Image
    Image.init()          # sem isso o codec JPEG pode não estar registrado
    imgs = []
    for c in caminhos:
        im = Image.open(c)
        imgs.append(im.convert("RGB") if im.mode != "RGB" else im)
    if not imgs:
        raise ValueError("Nenhuma imagem para juntar.")
    imgs[0].save(destino, save_all=True, append_images=imgs[1:])
    return destino


# ------------------------------------------- PDF → editável (.docx)

_DOC_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main"><w:body>{corpo}'
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134"'
            ' w:left="1134" w:header="709" w:footer="709" w:gutter="0"/>'
            '</w:sectPr></w:body></w:document>')

_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
         '2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
         'openxmlformats.org/officeDocument/2006/relationships/'
         'officeDocument" Target="word/document.xml"/></Relationships>')

_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
          'content-types"><Default Extension="rels" ContentType="application/'
          'vnd.openxmlformats-package.relationships+xml"/><Default '
          'Extension="xml" ContentType="application/xml"/><Override '
          'PartName="/word/document.xml" ContentType="application/vnd.'
          'openxmlformats-officedocument.wordprocessingml.document.main+xml"'
          '/></Types>')


def texto_para_docx(paragrafos: list[str], destino: str) -> str:
    corpo = []
    for t in paragrafos:
        corpo.append(
            '<w:p><w:pPr><w:spacing w:after="160" w:line="360" '
            'w:lineRule="auto"/><w:jc w:val="both"/></w:pPr><w:r><w:rPr>'
            '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>'
            '<w:sz w:val="24"/></w:rPr><w:t xml:space="preserve">'
            f'{escape(t)}</w:t></w:r></w:p>')
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml",
                   _DOC_XML.format(corpo="".join(corpo)))
    return destino


def _quebrar_paragrafos(texto: str) -> list[str]:
    """Remonta parágrafos do texto extraído.

    O PDF quebra linha por largura da página, não por fim de ideia: juntar
    tudo por linha em branco costuma render dois blocos gigantes. Aqui as
    linhas são emendadas até encontrar fim de frase ou linha curta.
    """
    blocos = [b for b in re.split(r"\n\s*\n", texto) if b.strip()]
    if len(blocos) >= 4:
        return [re.sub(r"\s+", " ", b).strip() for b in blocos]

    paragrafos, atual = [], ""
    for linha in texto.splitlines():
        l = linha.strip()
        if not l:
            if atual:
                paragrafos.append(atual.strip())
                atual = ""
            continue
        atual = f"{atual} {l}".strip()
        # fim de parágrafo: termina frase, ou é linha curta (título/rótulo)
        if l.endswith((".", ";", ":", "!", "?")) or len(l) < 45:
            paragrafos.append(atual.strip())
            atual = ""
    if atual:
        paragrafos.append(atual.strip())
    return [re.sub(r"\s+", " ", p) for p in paragrafos if p.strip()]


def pdf_para_docx(caminho: str, destino: str | None = None) -> tuple[str, str]:
    """Converte para .docx recuperando o TEXTO (não o layout).

    Devolve (arquivo, aviso) — o aviso é para ser mostrado à usuária.
    """
    texto = pdf_texto(caminho)
    destino = _saida(caminho, "", ".docx", destino)
    if not texto.strip():
        raise ValueError(
            "Este PDF não tem texto — parece digitalizado. Peça a "
            "transcrição por OCR: eu converto as páginas em imagem e leio.")
    paragrafos = _quebrar_paragrafos(texto)
    texto_para_docx(paragrafos, destino)
    return destino, ("O texto foi recuperado, mas o layout do PDF (colunas, "
                     "tabelas, posição de imagens) não é preservado — "
                     "confira a formatação.")


# ----------------------------------------- conversões que usam o Office

def docx_para_pdf(caminho: str, destino: str | None = None) -> str:
    from docx2pdf import convert
    destino = _saida(caminho, "", ".pdf", destino)
    convert(caminho, destino)
    if not os.path.exists(destino):
        raise RuntimeError("Não foi possível gerar o PDF (Word instalado?).")
    return destino


def pptx_para_pdf(caminho: str, destino: str | None = None) -> str:
    """Usa o PowerPoint instalado (Windows)."""
    import comtypes.client
    destino = _saida(caminho, "", ".pdf", destino)
    app = comtypes.client.CreateObject("Powerpoint.Application")
    try:
        pres = app.Presentations.Open(os.path.abspath(caminho), WithWindow=False)
        pres.SaveAs(os.path.abspath(destino), 32)   # 32 = PDF
        pres.Close()
    finally:
        app.Quit()
    return destino


def docx_para_pptx(caminho: str, destino: str | None = None,
                   titulo: str | None = None) -> str:
    """Transforma um relatório em apresentação: cada trecho vira um slide."""
    import apresentacao
    import docx_engine
    modelo = docx_engine.extract(caminho)
    destino = _saida(caminho, "", ".pptx", destino)

    slides, atual = [], None
    for p in modelo.paragraphs:
        if p.kind in ("title", "h"):
            if atual:
                slides.append(atual)
            atual = {"titulo": p.text.rstrip(":;"), "topicos": []}
        elif p.kind in ("p", "b", "quote", "field"):
            if atual is None:
                atual = {"titulo": "Conteúdo", "topicos": []}
            t = p.text
            atual["topicos"].append(t if len(t) <= 220 else t[:217] + "…")
            if len(atual["topicos"]) >= 6:
                slides.append(atual)
                atual = {"titulo": atual["titulo"] + " (cont.)",
                         "topicos": []}
    if atual and atual["topicos"]:
        slides.append(atual)

    plano = {"titulo": titulo or os.path.splitext(
        os.path.basename(caminho))[0].replace("_", " "),
        "subtitulo": "Gerado a partir do documento", "slides": slides}
    return apresentacao.criar(plano, destino)
