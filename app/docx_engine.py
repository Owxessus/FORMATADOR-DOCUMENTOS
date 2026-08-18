# -*- coding: utf-8 -*-
"""
Motor de documentos .docx do Formatador de Relatórios.

Pipeline:
  1. extract()  — abre o .docx, preserva cabeçalho/rodapé/assinaturas e extrai
                  os parágrafos editáveis do corpo, classificados por tipo.
  2. (correção) — o texto vai à IA fora deste módulo (ai_client) e volta como
                  lista de parágrafos corrigidos (mesmo tamanho; "" = excluir).
  3. build_final() / build_redline() — reconstroem o documento com formatação
                  padronizada; o redline usa alterações rastreadas nativas do
                  Word calculadas por diff palavra a palavra (determinístico).
  4. verify()   — confere que aceitar todas as revisões do redline reproduz
                  exatamente o texto da versão final.
"""
from __future__ import annotations

import difflib
import os
import re
import zipfile
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
AUTHOR = "Formatador (revisão)"
RDATE = "2024-01-01T12:00:00Z"  # data simbólica das revisões

BULLET_CHARS = "•◦▪·–-"

# ---------------------------------------------------------------- modelo


@dataclass
class Paragraph:
    kind: str          # date | title | field | h | b | p
    text: str          # texto original (limpo)
    corrected: str | None = None  # preenchido após a IA ("" = excluir)


@dataclass
class DocModel:
    src_path: str
    prefix: str                    # XML até <w:body> (inclusive)
    sectpr: str                    # <w:sectPr…> original
    paragraphs: list[Paragraph] = field(default_factory=list)
    signature_xml: str = ""        # zona de assinatura preservada verbatim
    signature_labels: list[str] | None = None  # rótulos vindos do perfil
    warnings: list[str] = field(default_factory=list)

    @property
    def editable_texts(self) -> list[str]:
        return [p.text for p in self.paragraphs]


# ---------------------------------------------------------------- extração


def _para_text(p_xml: str) -> str:
    """Concatena o texto visível de um parágrafo (ignora texto deletado)."""
    p_xml = re.sub(r"<w:del\b.*?</w:del>", "", p_xml, flags=re.S)
    parts = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", p_xml, flags=re.S)
    text = "".join(parts)
    for ent, ch in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&quot;", '"'), ("&apos;", "'")):
        text = text.replace(ent, ch)
    return text


def _split_paragraphs(body_xml: str) -> list[str]:
    """Divide o corpo em elementos <w:p>…</w:p> de nível superior."""
    out, depth, start = [], 0, None
    for m in re.finditer(r"<w:p\b[^>]*/>|<w:p\b[^>]*>|</w:p>", body_xml):
        tok = m.group(0)
        if tok.endswith("/>") and tok.startswith("<w:p"):
            if depth == 0:
                out.append(tok)
            continue
        if tok.startswith("<w:p"):
            if depth == 0:
                start = m.start()
            depth += 1
        else:
            depth -= 1
            if depth == 0 and start is not None:
                out.append(body_xml[start:m.end()])
                start = None
    return out


_DATE_RE = re.compile(
    r"^\s*[\wÀ-ú .]*?,\s*\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\s*\.?\s*$", re.I)
_FIELD_RE = re.compile(r"^\s*[A-ZÀ-Ú][^:\n]{0,40}:\s*\S")


def _classify(text: str, p_xml: str, index: int, total: int) -> str:
    t = text.strip()
    if _DATE_RE.match(t) and index <= 2:
        return "date"
    if len(t) <= 60 and index <= 8 and not t.endswith((".", ";", ",")) and (
            "relatório" in t.lower() or t.isupper()):
        return "title"
    if _FIELD_RE.match(t) and len(t.split(":")[0]) <= 40 and index <= 10:
        return "field"
    if "<w:numPr>" in p_xml or (t and t[0] in BULLET_CHARS and len(t) > 2):
        return "b"
    if len(t) <= 60 and t.endswith((":", ";")):
        return "h"
    return "p"


def _find_signature_start(paras: list[str]) -> int:
    """Índice onde começa a zona de assinatura (preservada verbatim).

    Varre DO FIM para o início aceitando parágrafos vazios, rótulos curtos
    (Gerente, Equipe Técnica…) e âncoras — imagem de assinatura ou linha de
    underscores. Para no primeiro parágrafo longo de texto corrido. Os
    rótulos vêm DEPOIS da linha de assinatura, por isso não se pode parar
    ao encontrá-los.
    """
    def is_anchor(p: str) -> bool:
        if "<a:blip" in p:          # imagem (assinatura digitalizada/logo)
            return True
        t = _para_text(p).strip()
        return bool(t) and set(t) <= set("_  ") and len(t) >= 5

    sig_start = len(paras)
    achou_ancora = False
    passos = 0
    for i in range(len(paras) - 1, -1, -1):
        t = _para_text(paras[i]).strip()
        if is_anchor(paras[i]):
            achou_ancora = True
            sig_start = i
            passos = 0
            continue
        if not t or len(t) <= 70:
            passos += 1
            if passos > 12:
                break
            continue
        break
    return sig_start if achou_ancora else len(paras)


def extract(docx_path: str) -> DocModel:
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")

    body_start = xml.index("<w:body>") + len("<w:body>")
    prefix = xml[:body_start]
    m_sect = re.search(r"<w:sectPr\b[^>]*>.*?</w:sectPr>|<w:sectPr\b[^>]*/>",
                       xml, flags=re.S)
    if not m_sect:
        raise ValueError("Documento sem <w:sectPr> — formato inesperado.")
    sectpr = m_sect.group(0)
    # margem superior mínima: evita que a 1ª linha encoste no timbre
    def _bump_top(m):
        return m.group(0) if int(m.group(1)) >= 2000 else \
            m.group(0).replace(f'w:top="{m.group(1)}"', 'w:top="2100"')
    sectpr = re.sub(r'<w:pgMar[^>]*w:top="(\d+)"[^>]*/>', _bump_top, sectpr)
    body = xml[body_start:m_sect.start()]

    paras = _split_paragraphs(body)
    sig_start = _find_signature_start(paras)

    model = DocModel(src_path=docx_path, prefix=prefix, sectpr=sectpr,
                     signature_xml="".join(paras[sig_start:]))

    texts: list[tuple[str, str]] = []
    for p in paras[:sig_start]:
        t = re.sub(r"\s+", " ", _para_text(p)).strip()
        if not t:
            continue  # parágrafos vazios: espaçamento agora é da formatação
        texts.append((t, p))

    # funde parágrafos quebrados no meio de frase (quebra de página no fonte)
    merged: list[tuple[str, str]] = []
    for t, p in texts:
        if merged and merged[-1][0][-1:].islower() and t[:1].islower() \
                and not _FIELD_RE.match(t) and "<w:numPr>" not in p \
                and t[0] not in BULLET_CHARS:
            pt, pp = merged[-1]
            merged[-1] = (pt + " " + t, pp)
        else:
            merged.append((t, p))

    total = len(merged)
    for i, (t, p) in enumerate(merged):
        kind = _classify(t, p, i, total)
        if kind == "b" and t and t[0] in BULLET_CHARS:
            t = t.lstrip(BULLET_CHARS).strip()
        model.paragraphs.append(Paragraph(kind=kind, text=t))
    return model


# ---------------------------------------------------------------- xml helpers

_id_counter = [1000]


def _nid() -> int:
    _id_counter[0] += 1
    return _id_counter[0]


def _rpr(bold=False, italic=False, sz=24) -> str:
    s = "<w:rPr>"
    s += ('<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"'
          ' w:cs="Times New Roman"/>')
    if bold:
        s += "<w:b/><w:bCs/>"
    if italic:
        s += "<w:i/><w:iCs/>"
    s += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/><w:lang w:val="pt-BR"/></w:rPr>'
    return s


def _run(text, **fmt) -> str:
    return f'<w:r>{_rpr(**fmt)}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _ins(text, **fmt) -> str:
    return (f'<w:ins w:id="{_nid()}" w:author="{AUTHOR}" w:date="{RDATE}">'
            f'<w:r>{_rpr(**fmt)}<w:t xml:space="preserve">{escape(text)}</w:t>'
            f"</w:r></w:ins>")


def _del(text, **fmt) -> str:
    return (f'<w:del w:id="{_nid()}" w:author="{AUTHOR}" w:date="{RDATE}">'
            f'<w:r>{_rpr(**fmt)}<w:delText xml:space="preserve">{escape(text)}'
            f"</w:delText></w:r></w:del>")


def _ppr(kind: str, bullet_numid: int | None) -> str:
    spacing = '<w:spacing w:after="200" w:line="360" w:lineRule="auto"/>'
    if kind == "date":
        return f'<w:pPr>{spacing}<w:jc w:val="right"/>{_rpr()}</w:pPr>'
    if kind == "title":
        return ('<w:pPr><w:spacing w:before="240" w:after="360" w:line="360"'
                f' w:lineRule="auto"/><w:jc w:val="center"/>{_rpr(bold=True, sz=28)}</w:pPr>')
    if kind == "field":
        return ('<w:pPr><w:spacing w:after="80" w:line="360" w:lineRule="auto"/>'
                f'<w:jc w:val="left"/>{_rpr()}</w:pPr>')
    if kind == "h":
        return f'<w:pPr>{spacing}<w:jc w:val="both"/>{_rpr(bold=True)}</w:pPr>'
    if kind == "b":
        num = (f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{bullet_numid}"/></w:numPr>'
               if bullet_numid else "")
        return ('<w:pPr>' + num +
                '<w:spacing w:after="120" w:line="360" w:lineRule="auto"/>'
                '<w:ind w:left="1077" w:hanging="357"/>'
                f'<w:jc w:val="both"/>{_rpr(italic=True)}</w:pPr>')
    return (f'<w:pPr>{spacing}<w:ind w:firstLine="709"/>'
            f'<w:jc w:val="both"/>{_rpr()}</w:pPr>')


def _fmt_for(kind: str) -> dict:
    if kind == "title":
        return dict(bold=True, sz=28)
    if kind == "h":
        return dict(bold=True)
    if kind == "b":
        return dict(italic=True)
    return {}


def _clean_par(kind: str, text: str, bullet_numid) -> str:
    fmt = _fmt_for(kind)
    if kind == "field" and ":" in text:
        label, rest = text.split(":", 1)
        runs = _run(label + ":", bold=True) + _run(rest)
    elif kind == "b" and not bullet_numid:
        runs = _run("–  " + text, **fmt)  # fallback sem numbering
    else:
        runs = _run(text, **fmt)
    return f"<w:p>{_ppr(kind, bullet_numid)}{runs}</w:p>"


def _tokenize(t: str) -> list[str]:
    return re.findall(r"\S+\s*|\s+", t)


def _redline_par(kind: str, orig: str, corr: str, bullet_numid) -> str:
    fmt = _fmt_for(kind)
    if corr == "":
        pp = _ppr(kind, bullet_numid).replace(
            "<w:rPr>",
            f'<w:rPr><w:del w:id="{_nid()}" w:author="{AUTHOR}" w:date="{RDATE}"/>',
            1)
        return f"<w:p>{pp}{_del(orig, **fmt)}</w:p>"
    a, b = _tokenize(orig), _tokenize(corr)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    parts = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            parts.append(_run("".join(a[i1:i2]), **fmt))
        else:
            if i2 > i1:
                parts.append(_del("".join(a[i1:i2]), **fmt))
            if j2 > j1:
                parts.append(_ins("".join(b[j1:j2]), **fmt))
    return f"<w:p>{_ppr(kind, bullet_numid)}{''.join(parts)}</w:p>"


FORMAT_NOTE = [
    "NOTA DA REVISÃO — ALTERAÇÕES DE FORMATAÇÃO APLICADAS (além das correções de texto marcadas acima):",
    "1. Texto justificado em todos os parágrafos, com recuo de primeira linha (1,25 cm);",
    "2. Espaçamento entre linhas de 1,5 e espaço uniforme entre parágrafos;",
    "3. Fonte padronizada em Times New Roman 12; título centralizado em destaque;",
    "4. Data alinhada à direita; rótulos de cabeçalho e subtítulos em negrito;",
    "5. Listas convertidas em marcadores padronizados, quando presentes;",
    "6. Bloco de assinatura preservado do documento original.",
    "Esta nota é apenas informativa e pode ser excluída ao aceitar/rejeitar as revisões.",
]


def _fmt_note() -> str:
    out = ['<w:p><w:pPr><w:spacing w:after="200"/></w:pPr>'
           '<w:r><w:br w:type="page"/></w:r></w:p>']
    for i, t in enumerate(FORMAT_NOTE):
        bold = i == 0
        mark = f'<w:ins w:id="{_nid()}" w:author="{AUTHOR}" w:date="{RDATE}"/>'
        prr = _rpr(bold=bold).replace("<w:rPr>", "<w:rPr>" + mark, 1)
        out.append('<w:p><w:pPr><w:spacing w:after="120" w:line="360"'
                   f' w:lineRule="auto"/><w:jc w:val="both"/>{prr}</w:pPr>'
                   f"{_ins(t, bold=bold)}</w:p>")
    return "".join(out)


# ------------------------------------------------------- numbering (bullets)

_BULLET_ABSTRACT = ('<w:abstractNum w:abstractNumId="{aid}">'
                    '<w:multiLevelType w:val="singleLevel"/>'
                    '<w:lvl w:ilvl="0"><w:start w:val="1"/>'
                    '<w:numFmt w:val="bullet"/><w:lvlText w:val=""/>'
                    '<w:lvlJc w:val="left"/>'
                    '<w:pPr><w:ind w:left="1077" w:hanging="357"/></w:pPr>'
                    '<w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"'
                    ' w:hint="default"/></w:rPr></w:lvl></w:abstractNum>')


def _ensure_bullet_numbering(files: dict) -> int | None:
    """Garante um numId de lista com marcador; devolve o numId."""
    name = "word/numbering.xml"
    if name in files:
        xml = files[name].decode("utf-8")
        for m in re.finditer(r'<w:num w:numId="(\d+)"[^>]*>\s*'
                             r'<w:abstractNumId w:val="(\d+)"', xml):
            aid = m.group(2)
            am = re.search(
                rf'<w:abstractNum w:abstractNumId="{aid}".*?</w:abstractNum>',
                xml, flags=re.S)
            if am and '<w:numFmt w:val="bullet"' in am.group(0):
                return int(m.group(1))
        aids = [int(a) for a in re.findall(r'w:abstractNumId="(\d+)"', xml)]
        nids = [int(n) for n in re.findall(r'<w:num w:numId="(\d+)"', xml)]
        aid, nid = max(aids or [0]) + 1, max(nids or [0]) + 1
        abstract = _BULLET_ABSTRACT.format(aid=aid)
        if "<w:num " in xml:
            xml = xml.replace("<w:num ", abstract + "<w:num ", 1)
        else:
            xml = xml.replace("</w:numbering>", abstract + "</w:numbering>")
        xml = xml.replace(
            "</w:numbering>",
            f'<w:num w:numId="{nid}"><w:abstractNumId w:val="{aid}"/></w:num>'
            "</w:numbering>")
        files[name] = xml.encode("utf-8")
        return nid
    # cria numbering.xml do zero
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<w:numbering xmlns:w="{W_NS}">' + _BULLET_ABSTRACT.format(aid=1) +
           '<w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num></w:numbering>')
    files[name] = xml.encode("utf-8")
    rels = files["word/_rels/document.xml.rels"].decode("utf-8")
    if "numbering.xml" not in rels:
        rels = rels.replace(
            "</Relationships>",
            '<Relationship Id="rIdNum999" Type="http://schemas.openxmlformats.'
            'org/officeDocument/2006/relationships/numbering" '
            'Target="numbering.xml"/></Relationships>')
        files["word/_rels/document.xml.rels"] = rels.encode("utf-8")
    ct = files["[Content_Types].xml"].decode("utf-8")
    if "numbering+xml" not in ct:
        ct = ct.replace(
            "</Types>",
            '<Override PartName="/word/numbering.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
            "</Types>")
        files["[Content_Types].xml"] = ct.encode("utf-8")
    return 1


# ---------------------------------------------------------------- montagem


def _load_files(docx_path: str) -> dict:
    with zipfile.ZipFile(docx_path) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def _write_docx(files: dict, out_path: str) -> None:
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        if "[Content_Types].xml" in files:
            z.writestr("[Content_Types].xml", files["[Content_Types].xml"])
        for n, data in files.items():
            if n != "[Content_Types].xml":
                z.writestr(n, data)


def override_signature(sig_xml: str, labels: list[str]) -> str:
    """Troca os rótulos da assinatura (Gerente / Equipe Técnica…),
    preservando imagens e a linha de assinatura do documento original."""
    if not labels:
        return sig_xml
    mantidos = []
    for p in _split_paragraphs(sig_xml):
        t = _para_text(p).strip()
        if "<a:blip" in p or (t and set(t) <= set("_  ")):
            mantidos.append(p)
    centro = ('<w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
              f'<w:jc w:val="center"/>{_rpr(bold=True)}</w:pPr>')
    novos = [f"<w:p>{centro}{_run(l, bold=True)}</w:p>" for l in labels]
    return "".join(mantidos + novos)


def _build(model: DocModel, out_path: str, redline: bool) -> None:
    files = _load_files(model.src_path)
    has_bullets = any(p.kind == "b" for p in model.paragraphs)
    numid = _ensure_bullet_numbering(files) if has_bullets else None
    body = []
    for p in model.paragraphs:
        corr = p.corrected if p.corrected is not None else p.text
        if corr == "" and not redline:
            continue
        if redline and corr != p.text:
            body.append(_redline_par(p.kind, p.text, corr, numid))
        else:
            body.append(_clean_par(p.kind, corr, numid))
    sig = model.signature_xml
    if model.signature_labels:
        sig = override_signature(sig, model.signature_labels)
    body.append(sig)
    if redline:
        body.append(_fmt_note())
    xml = model.prefix + "".join(body) + model.sectpr + "</w:body></w:document>"
    files["word/document.xml"] = xml.encode("utf-8")
    _write_docx(files, out_path)


def build_final(model: DocModel, out_path: str) -> None:
    _build(model, out_path, redline=False)


def build_redline(model: DocModel, out_path: str) -> None:
    _build(model, out_path, redline=True)


# ------------------------------------------------------------- verificação


def _visible_text(doc_xml: str, accept: bool) -> str:
    """Texto do corpo com revisões aceitas (accept=True) ou como está."""
    x = doc_xml
    if accept:
        x = re.sub(r"<w:del\b[^>]*>.*?</w:del>", "", x, flags=re.S)
    m = re.search(r"<w:body>(.*)</w:body>", x, flags=re.S)
    x = m.group(1) if m else x
    x = x.split("NOTA DA REVISÃO")[0]
    parts = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", x, flags=re.S)
    text = re.sub(r"\s+", " ", " ".join(parts)).strip()
    for ent, ch in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&quot;", '"'), ("&apos;", "'")):
        text = text.replace(ent, ch)
    return text


def verify(final_path: str, redline_path: str) -> bool:
    """True se aceitar todas as revisões do redline == versão final."""
    with zipfile.ZipFile(final_path) as z:
        final_xml = z.read("word/document.xml").decode("utf-8")
    with zipfile.ZipFile(redline_path) as z:
        red_xml = z.read("word/document.xml").decode("utf-8")
    return _visible_text(final_xml, accept=False) == _visible_text(red_xml, accept=True)


# --------------------------------------------------- proteção de números


def numbers_of(text: str) -> list[str]:
    return sorted(re.findall(r"\d+", text))


def numbers_preserved(orig: str, corr: str) -> bool:
    if corr == "":
        return True
    return numbers_of(orig) == numbers_of(corr)


# ---------------------------------------------------------------- pipeline


def process(docx_path: str, corrector, out_dir: str | None = None,
            extra_instructions: str = "",
            progress=lambda msg: None,
            signature_labels: list[str] | None = None,
            checkers=()) -> dict:
    """
    Pipeline completo. `corrector(texts, kinds, extra_instructions)` deve
    devolver a lista de textos corrigidos (mesmo tamanho; "" = excluir).
    """
    progress("Lendo documento…")
    model = extract(docx_path)
    if not model.paragraphs:
        raise ValueError("Nenhum parágrafo de texto encontrado no documento.")

    model.signature_labels = signature_labels

    progress("Conferindo datas e blocos institucionais…")
    for fn in checkers:
        try:
            model.warnings.extend(fn(model.editable_texts))
        except Exception as e:  # noqa: BLE001 — verificação nunca bloqueia
            model.warnings.append(f"Verificação não pôde ser feita: {e}")

    progress("Corrigindo texto com IA…")
    kinds = [p.kind for p in model.paragraphs]
    corrected = corrector(model.editable_texts, kinds, extra_instructions)
    if len(corrected) != len(model.paragraphs):
        raise ValueError("A correção devolveu número inesperado de parágrafos.")

    for p, corr in zip(model.paragraphs, corrected):
        if not numbers_preserved(p.text, corr):
            model.warnings.append(
                f"Números alterados pela IA foram revertidos em: “{p.text[:60]}…”")
            corr = p.text
        p.corrected = corr

    base = os.path.splitext(os.path.basename(docx_path))[0]
    out_dir = out_dir or os.path.dirname(os.path.abspath(docx_path))
    final_path = os.path.join(out_dir, f"{base}_FINAL.docx")
    redline_path = os.path.join(out_dir, f"{base}_ALTERACOES_RASTREADAS.docx")

    progress("Gerando versão final…")
    build_final(model, final_path)
    progress("Gerando versão com alterações rastreadas…")
    build_redline(model, redline_path)

    progress("Verificando consistência…")
    ok = verify(final_path, redline_path)
    if not ok:
        model.warnings.append("Autoverificação falhou: revise o diff antes de usar.")

    return {"final": final_path, "redline": redline_path,
            "verified": ok, "warnings": model.warnings,
            "texto": " ".join(p.corrected or p.text for p in model.paragraphs),
            "paragraphs": len(model.paragraphs),
            "changed": sum(1 for p in model.paragraphs
                           if p.corrected not in (None, p.text))}
