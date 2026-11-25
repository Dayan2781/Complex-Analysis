#!/usr/bin/env python3
"""Комплекс анализын LaTeX лекцийг PreTeXt XML болгох хөрвүүлэгч.

Эх LaTeX файлуудад хэрэглэгдсэн цөөн тооны орчин, командыг л таньдаг
(thm, dfn, exm, sol, prf, equation, eqnarray, align, enumerate, ...).
Номын бүтцийг (аль файлын аль мөрүүд аль бүлэгт орох) build_book.py тодорхойлно.
"""
from __future__ import annotations

import re

# ── Туслах функцууд ────────────────────────────────────────────────


def xesc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def match_brace(s: str, i: int) -> int:
    """s[i] == '{' бол харгалзах '}'-ийн индексийг буцаана."""
    assert s[i] == "{", s[i:i + 30]
    depth = 0
    j = i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    raise ValueError("unbalanced braces: " + s[i:i + 80])


def match_bracket(s: str, i: int) -> int:
    assert s[i] == "["
    depth = 0
    j = i
    while j < len(s):
        c = s[j]
        if c == "{":
            j = match_brace(s, j) + 1
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    raise ValueError("unbalanced brackets")


def strip_command(s: str, name: str, keep_arg: bool = False) -> str:
    """\\name{...} командыг устгах (эсвэл аргументаар нь солих)."""
    out = []
    pat = re.compile(r"\\" + name + r"\*?\s*(?=\{)")
    pos = 0
    for m in pat.finditer(s):
        if m.start() < pos:
            continue
        out.append(s[pos:m.start()])
        b = m.end()
        e = match_brace(s, b)
        if keep_arg:
            out.append(s[b + 1:e])
        pos = e + 1
    out.append(s[pos:])
    return "".join(out)


def find_env_end(s: str, name: str, start: int) -> tuple[int, int]:
    """start нь \\begin{name}-ийн дараах байрлал. (content_end, after_end) буцаана."""
    pat = re.compile(r"\\(begin|end)\{" + re.escape(name) + r"\}")
    depth = 1
    for m in pat.finditer(s, start):
        depth += 1 if m.group(1) == "begin" else -1
        if depth == 0:
            return m.start(), m.end()
    raise ValueError(f"no \\end{{{name}}} after: " + s[start:start + 80])


# ── Шошго (label) ба лавлагаа (ref) ───────────────────────────────


def label_id(prefix: str, label: str) -> str:
    """LaTeX шошгыг PreTeXt-д хүчинтэй (ASCII) xml:id болгоно."""
    out = []
    for c in label.strip():
        if c.isascii() and (c.isalnum() or c in "-_"):
            out.append(c)
        elif c in ". ":
            out.append("_")
        else:
            out.append(f"u{ord(c):x}")
    return prefix + "-" + "".join(out)


class Ctx:
    def __init__(self, prefix: str, images: set[str] | None = None):
        self.prefix = prefix
        self.ids: set[str] = set()
        self.kinds: dict[str, str] = {}
        self.images = images if images is not None else set()

    def make_id(self, label: str, kind: str) -> str:
        lid = label_id(self.prefix, label)
        if lid in self.ids:
            return ""
        self.ids.add(lid)
        self.kinds[lid] = kind
        return lid


def ref_placeholder(ctx: Ctx, label: str) -> str:
    return f"@@REF:{label_id(ctx.prefix, label)}@@"


def resolve_refs(xml: str, all_ids: dict[str, str]) -> str:
    def rep(m):
        lid = m.group(1)
        if lid not in all_ids:
            return "(?)"
        if all_ids[lid] == "eq":
            return f'<xref ref="{lid}"/>'
        return f'<xref ref="{lid}" text="global"/>'
    # Тэгшитгэлийн лавлагааны эргэн тойрны хаалтыг авна (xref өөрөө хаалт тавина)
    xml = re.sub(r"\(\s*(@@REF:[^@]*@@)\s*\)", r"\1", xml)
    return re.sub(r"@@REF:([^@]*)@@", rep, xml)


# ── Математик ─────────────────────────────────────────────────────


def clean_math(m: str, ctx: Ctx) -> tuple[str, str]:
    """Математик текстийг цэвэрлээд (math, label) буцаана."""
    label = ""
    lm = re.search(r"\\label\{([^}]*)\}", m)
    if lm:
        label = lm.group(1)
    m = re.sub(r"\\label\{[^}]*\}", "", m)
    m = strip_command(m, "index")
    m = m.replace("\\nonumber", "").replace("\\normalfont", "")
    m = re.sub("\x01alert\x02", r"\\mathbf{", m)
    m = re.sub("\x01\\w+\x02", r"\\text{", m)
    m = re.sub("\x01/\\w+\x02", "}", m)
    m = re.sub(r"\\ref\{([^}]*)\}", "?", m)
    m = re.sub(r"\\hfill", "", m)
    m = m.replace("\\displaystyleint", "\\displaystyle\\int")
    return m.strip(), label


def display_math(env: str, body: str, ctx: Ctx) -> str:
    """Дэлгэцийн томьёо → <me>, <men>, <md>, <mdn>."""
    body = re.sub(r"\\begin\{(split|aligned)\}|\\end\{(split|aligned)\}", "", body)
    multi = env in ("eqnarray", "eqnarray*", "align", "align*", "gather", "gather*", "multline", "multline*") \
        or (re.search(r"(?<!\\)\\\\", body) and "&" in body and not re.search(r"\\begin\{(cases|array|pmatrix|vmatrix|matrix|bmatrix)\}", body))
    numbered_env = env in ("equation", "eqnarray", "align", "gather")
    if not multi:
        m, label = clean_math(body, ctx)
        m = re.sub(r"\\tag\{[^}]*\}", "", m) if label else m
        if label:
            lid = ctx.make_id(label, "eq")
            if lid:
                return f'<men xml:id="{lid}">{xesc(m)}</men>'
        return f"<me>{xesc(m)}</me>"
    # олон мөртэй
    rows = re.split(r"(?<!\\)\\\\(?:\[[^\]]*\])?", body)
    out_rows = []
    any_label = False
    for r in rows:
        if not r.strip():
            continue
        m, label = clean_math(r, ctx)
        if env.startswith("eqnarray"):
            m = re.sub(r"&\s*([=<>]|\\leq|\\geq|\\le|\\ge|\\neq|\\approx|\\sim|\\equiv|\\Rightarrow|\\Leftrightarrow|\\to)\s*&", r"&\1 ", m)
            m = m.replace("&&", "&")
        if label:
            lid = ctx.make_id(label, "eq")
            if lid:
                any_label = True
                out_rows.append(f'<mrow xml:id="{lid}">{xesc(m)}</mrow>')
                continue
        out_rows.append(f"<mrow>{xesc(m)}</mrow>")
    if not out_rows:
        return ""
    if any_label:
        out_rows = [r if "xml:id" in r else r.replace("<mrow>", '<mrow number="no">') for r in out_rows]
        return "<mdn>" + "".join(out_rows) + "</mdn>"
    return "<md>" + "".join(out_rows) + "</md>"


# ── Мөр доторх текст ─────────────────────────────────────────────

CIRCLED = {str(i): chr(0x2460 + i - 1) for i in range(1, 10)}


def text_part(t: str, ctx: Ctx) -> str:
    """Математик биш текстийг XML болгоно."""
    t = strip_command(t, "index")
    t = re.sub(r"\\label\{[^}]*\}", "", t)
    t = re.sub(r"\\ref\{([^}]*)\}", lambda m: ref_placeholder(ctx, m.group(1)), t)
    t = re.sub(r"\\circled\{(\d)\}", lambda m: CIRCLED.get(m.group(1), m.group(1)), t)
    t = re.sub(r"\\(newpage|centering|noindent|hfill|qquad|quad|smallskip|medskip|bigskip|morshilj|par|tiny|small|large|Large|normalfont|bf|it|item)\b\s*", " ", t)
    t = re.sub(r"\\(vspace|hspace)\*?\{[^}]*\}", " ", t)
    t = t.replace("\\\\", " ")
    t = t.replace("``", "“").replace("''", "”").replace("---", "—").replace("--", "–")
    t = t.replace("~", " ")
    for a, b in [("\\%", "%"), ("\\&", "&"), ("\\_", "_"), ("\\{", "{"), ("\\}", "}"), ("\\#", "#"), ("\\,", " "), ("\\ ", " ")]:
        t = t.replace(a, b)
    t = xesc(t)
    t = re.sub("\x01(/?)(\\w+)\x02", r"<\1\2>", t)
    # Аргументтай командууд
    for name, tag in [("textbf", "alert"), ("emph", "em"), ("textit", "em"), ("ind", "term"),
                      ("underline", "em"), ("footnote", "fn"), ("textsc", ""), ("textrm", ""),
                      ("text", ""), ("textup", ""), ("mbox", ""), ("textcolor", None)]:
        while True:
            m = re.search(r"\\" + name + r"\s*\{", t)
            if not m:
                break
            b = m.end() - 1
            if name == "textcolor":
                e = match_brace(t, b)
                b2 = e + 1
                e2 = match_brace(t, b2)
                t = t[:m.start()] + t[b2 + 1:e2] + t[e2 + 1:]
                continue
            e = match_brace(t, b)
            inner = t[b + 1:e]
            rep = f"<{tag}>{inner}</{tag}>" if tag else inner
            t = t[:m.start()] + rep + t[e + 1:]
    t = re.sub(r"\{\\(bf|it|em)\s+([^{}]*)\}", lambda m: f"<{'alert' if m.group(1) == 'bf' else 'em'}>{m.group(2)}</{'alert' if m.group(1) == 'bf' else 'em'}>", t)
    t = re.sub(r"\\[a-zA-Z]+\*?", "", t)  # танигдаагүй команд
    t = t.replace("{", "").replace("}", "")
    return t


def inline(s: str, ctx: Ctx) -> str:
    """Догол мөрийн текст: $...$ → <m>, бусад → text_part."""
    out = []
    i = 0
    n = len(s)
    buf = []
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n and s[i + 1] in "$()":
            if s[i + 1] == "$":
                buf.append("\\$")
                i += 2
                continue
            if s[i + 1] == "(":
                j = s.find("\\)", i + 2)
                if j > 0:
                    out.append(text_part("".join(buf), ctx)); buf = []
                    m, _ = clean_math(s[i + 2:j], ctx)
                    out.append(f"<m>{xesc(m)}</m>")
                    i = j + 2
                    continue
        if c == "\\" and i + 1 < n:
            buf.append(s[i:i + 2])
            i += 2
            continue
        if c == "$":
            j = i + 1
            while j < n:
                if s[j] == "\\":
                    j += 2
                    continue
                if s[j] == "$":
                    break
                j += 1
            out.append(text_part("".join(buf), ctx)); buf = []
            m, _ = clean_math(s[i + 1:j], ctx)
            if m:
                out.append(f"<m>{xesc(m)}</m>")
            i = j + 1
            continue
        buf.append(c)
        i += 1
    out.append(text_part("".join(buf), ctx))
    res = "".join(out)
    res = res.replace("\\$", "$")
    return res


# ── Блок түвшний хөрвүүлэлт ──────────────────────────────────────

THM = {"thm": "theorem", "lem": "lemma", "cor": "corollary", "prop": "proposition",
       "axm": "axiom", "sen": "fact", "dfn": "definition", "note": "remark",
       "hnt": "note", "prb": "exercise"}
DISPLAY = ("equation", "equation*", "eqnarray", "eqnarray*", "align", "align*",
           "gather", "gather*", "multline", "multline*", "displaymath")
LISTS = ("enumerate", "itemize", "description")
FIG = ("center", "figure", "minipage", "flushleft", "flushright")


def list_xml(env: str, body: str, ctx: Ctx, cols: int = 0) -> str:
    # дээд түвшний \item-уудыг олох
    items = []
    depth = 0
    pos = 0
    starts = []
    for m in re.finditer(r"\\begin\{[^}]*\}|\\end\{[^}]*\}|\\item\b", body):
        tok = m.group(0)
        if tok.startswith("\\begin"):
            depth += 1
        elif tok.startswith("\\end"):
            depth -= 1
        elif depth == 0:
            starts.append(m.start())
    if not starts:
        return flow(body, ctx)
    pre = body[:starts[0]]
    for k, st in enumerate(starts):
        en = starts[k + 1] if k + 1 < len(starts) else len(body)
        items.append(body[st + len("\\item"):en])
    lis = []
    labeled = False
    for it in items:
        label = ""
        s = it.lstrip()
        if s.startswith("["):
            e = match_bracket(s, 0)
            label = s[1:e].strip()
            s = s[e + 1:]
            labeled = True
        content = flow(s, ctx, in_li=True)
        if label:
            lab = inline(label, ctx)
            if content.startswith("<p>"):
                content = f"<p><alert>{lab}</alert> " + content[3:]
            else:
                content = f"<p><alert>{lab}</alert></p>" + content
        lis.append(f"<li>{content}</li>")
    attrs = f' cols="{cols}"' if cols else ""
    if labeled or env == "description":
        tag = f'<ul marker=""{attrs}>'
        close = "</ul>"
    elif env == "enumerate":
        tag, close = f"<ol{attrs}>", "</ol>"
    else:
        tag, close = f"<ul{attrs}>", "</ul>"
    pre_xml = inline(pre, ctx).strip()
    return (pre_xml + " " if pre_xml else "") + tag + "".join(lis) + close


def tabular_xml(body: str, ctx: Ctx) -> str:
    body = re.sub(r"\\hline|\\cline\{[^}]*\}", "", body)
    rows = [r for r in re.split(r"(?<!\\)\\\\", body) if r.strip()]
    out = []
    for r in rows:
        cells = re.split(r"(?<!\\)&", r)
        out.append("<row>" + "".join(f"<cell>{inline(c.strip(), ctx)}</cell>" for c in cells) + "</row>")
    return "<tabular>" + "".join(out) + "</tabular>"


def figure_xml(body: str, ctx: Ctx) -> str:
    """center/figure/minipage доторх зураг, tikz, caption."""
    parts = []
    caption = ""
    cm = re.search(r"\\caption(?:of\{figure\})?\s*\{", body)
    if cm:
        e = match_brace(body, cm.end() - 1)
        caption = body[cm.end():e]
        body = body[:cm.start()] + body[e + 1:]
    images = []
    for m in re.finditer(r"\\includegraphics\s*(\[[^\]]*\])?\s*\{([^}]*)\}", body):
        opts, path = m.group(1) or "", m.group(2).strip()
        w = 50
        wm = re.search(r"width\s*=\s*([\d.]+)\s*cm", opts)
        if wm:
            w = min(90, max(20, round(float(wm.group(1)) / 13 * 100)))
        wm2 = re.search(r"width\s*=\s*([\d.]+)\\(textwidth|linewidth)", opts)
        if wm2:
            w = min(90, round(float(wm2.group(1)) * 100))
        name = path.split("/")[-1]
        ctx.images.add(name)
        images.append(f'<image source="images/{name}" width="{w}%"/>')
    for m in re.finditer(r"\\begin\{tikzpicture\}", body):
        ce, ae = find_env_end(body, "tikzpicture", m.end())
        tikz = body[m.start():ae]
        images.append(f'<image width="50%"><latex-image>{xesc(tikz)}</latex-image></image>')
    rest = re.sub(r"\\includegraphics\s*(\[[^\]]*\])?\s*\{[^}]*\}", "", body)
    rest = re.sub(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", "", rest, flags=re.S)
    if images:
        for k, img in enumerate(images):
            cap = inline(caption, ctx).strip() if k == len(images) - 1 else ""
            parts.append(f"<figure><caption>{cap}</caption>{img}</figure>")
    rest = re.sub(r"\\(centering|label\{[^}]*\})", "", rest)
    if rest.strip():
        parts.insert(0, blocks(rest, ctx))
    return "".join(parts)


def flow(s: str, ctx: Ctx, in_li: bool = False) -> str:
    """Блок орчингүй текстийг <p> догол мөрүүд болгоно (томьёо, жагсаалт доторх)."""
    tokens: list[str] = []

    def stash(x: str) -> str:
        tokens.append(x)
        return f"\x00{len(tokens) - 1}\x00"

    out = []
    i = 0
    n = len(s)
    pat = re.compile(r"\$\$|\\\[|\\begin\{([a-zA-Z*]+)\}(\{\d+\})?")
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(s[i:])
            break
        tok = m.group(0)
        if tok == "$$":
            j = s.find("$$", m.end())
            if j < 0:
                out.append(s[i:])
                break
            out.append(s[i:m.start()])
            out.append(stash(display_math("displaymath", s[m.end():j], ctx)))
            i = j + 2
            continue
        if tok == "\\[":
            j = s.find("\\]", m.end())
            if j < 0:
                out.append(s[i:])
                break
            out.append(s[i:m.start()])
            out.append(stash(display_math("displaymath", s[m.end():j], ctx)))
            i = j + 2
            continue
        env = m.group(1)
        ce, ae = find_env_end(s, env, m.end())
        body = s[m.end():ce]
        out.append(s[i:m.start()])
        if env in DISPLAY:
            out.append(stash(display_math(env, body, ctx)))
        elif env in LISTS:
            out.append(stash(list_xml(env, body, ctx)))
        elif env == "multicols":
            cols = int((m.group(2) or "{2}")[1:-1])
            inner = body.strip()
            lm = re.match(r"\\begin\{(enumerate|itemize)\}", inner)
            if lm:
                lce, lae = find_env_end(inner, lm.group(1), lm.end())
                out.append(stash(list_xml(lm.group(1), inner[lm.end():lce], ctx, cols)))
                out.append(inner[lae:])
            else:
                out.append(body)
        elif env == "tabular":
            body2 = re.sub(r"^\s*\{[^}]*\}", "", body)
            out.append("\n\n" + stash("@@BLOCK@@" + tabular_xml(body2, ctx)) + "\n\n")
        elif env in ("array", "cases"):
            out.append(stash(f"<me>{xesc(clean_math(tok + body + '\\end{' + env + '}', ctx)[0])}</me>"))
        else:
            # flow дотор таарсан блок орчин — блок болгоно
            out.append("\n\n" + stash("@@BLOCK@@" + blocks(s[m.start():ae], ctx)) + "\n\n")
        i = ae
    text = "".join(out)
    text = text.replace("\\\\\n", "\n\n") if False else text
    paras = re.split(r"\n\s*\n", text)
    res = []
    for p in paras:
        if not p.strip():
            continue
        if re.fullmatch(r"\s*\x00(\d+)\x00\s*", p) and tokens[int(re.fullmatch(r"\s*\x00(\d+)\x00\s*", p).group(1))].startswith("@@BLOCK@@"):
            res.append(tokens[int(re.fullmatch(r"\s*\x00(\d+)\x00\s*", p).group(1))][9:])
            continue
        x = inline(p, ctx).strip()
        x = re.sub(r"\x00(\d+)\x00", lambda mm: tokens[int(mm.group(1))], x)
        if not re.sub(r"<[^>]+>", "", x).strip() and "<m" not in x and "<li" not in x and "<me" not in x and "<md" not in x:
            continue
        res.append(f"<p>{x}</p>")
    return "".join(res)


def env_title(body: str, ctx: Ctx) -> tuple[str, str]:
    """\\begin{thm}[Гарчиг] эсвэл эхэнд \\textbf{(Гарчиг).}"""
    title = ""
    s = body.lstrip()
    if s.startswith("["):
        e = match_bracket(s, 0)
        title = s[1:e]
        s = s[e + 1:]
    else:
        m = re.match("\x01alert\x02(.*?)\x01/alert\x02", s, re.S)
        if m:
            e = m.end() - 1
            cand = m.group(1).strip()
            plain = re.sub(r"\\index\{[^}]*\}", "", cand).strip()
            if len(plain) < 70 and plain:
                title = plain.strip(" ().").strip()
                s = s[e + 1:].lstrip(" .)")
    title = re.sub(r"\\index\{[^}]*\}", "", title).strip().strip("().").strip()
    return (inline(title, ctx) if title else ""), s


def blocks(s: str, ctx: Ctx) -> str:
    """Блок түвшний хөрвүүлэлт: теорем төст орчин, зураг, бусад нь flow."""
    out = []
    i = 0
    names = set(list(THM) + ["exm", "sol", "prf", "proof"] + list(FIG) + ["qbox", "solbox", "tcolorbox"])
    pat = re.compile(r"\\begin\{([a-zA-Z*]+)\}")
    flow_start = 0
    while True:
        m = pat.search(s, i)
        if not m:
            out.append(("flow", s[flow_start:]))
            break
        env = m.group(1)
        ce, ae = find_env_end(s, env, m.end())
        if env in names:
            out.append(("flow", s[flow_start:m.start()]))
            out.append((env, s[m.end():ce]))
            flow_start = ae
        i = ae
    res = []
    for kind, body in out:
        if kind == "flow":
            x = flow(body, ctx)
            if x:
                res.append(x)
            continue
        if kind in THM or kind == "exm":
            tag = THM.get(kind, "example")
            title, rest = env_title(body, ctx)
            label = ""
            lm = re.search(r"\\label\{([^}]*)\}", rest[:200])
            if lm:
                label = lm.group(1)
                rest = rest[:lm.start()] + rest[lm.end():]
            lid = ctx.make_id(label, tag) if label else ""
            idattr = f' xml:id="{lid}"' if lid else ""
            t = f"<title>{title}</title>" if title else ""
            stmt = blocks(rest, ctx) or "<p/>"
            if tag == "exercise":
                res.append(f"<exercise{idattr}>{t}<statement>{stmt}</statement></exercise>")
            else:
                res.append(f"<{tag}{idattr}>{t}<statement>{stmt}</statement></{tag}>")
            continue
        if kind in ("prf", "proof", "sol"):
            child = "solution" if kind == "sol" else "proof"
            inner = blocks(body, ctx) or "<p/>"
            inner = re.sub(r"<p>\s*(<m>\\blacksquare</m>|■)?\s*</p>", "", inner)
            # өмнөх (зөвхөн хоосон зай) блокт хавсаргах
            if res:
                prev = res[-1]
                mt = re.match(r"<(theorem|lemma|corollary|proposition|fact|example)\b", prev)
                if mt and ((child == "proof" and mt.group(1) != "example") or (child == "solution" and mt.group(1) == "example")):
                    close = f"</{mt.group(1)}>"
                    res[-1] = prev[: -len(close)] + f"<{child}>{inner}</{child}>" + close
                    continue
            if child == "proof":
                res.append(f"<proof>{inner}</proof>")
            else:
                res.append(f"<remark><title>Бодолт</title>{inner}</remark>")
            continue
        if kind in FIG:
            body = re.sub(r"^\s*\[[^\]]*\]", "", body)
            if kind == "minipage":
                body = re.sub(r"^\s*(\[[^\]]*\])?\s*\{[^}]*\}", "", body)
            res.append(figure_xml(body, ctx))
            continue
        # бусад хайрцаг
        res.append(flow(body, ctx))
    return "".join(res)


# ── Бүлэг/хэсэг ─────────────────────────────────────────────────


FMT = {"textbf": "alert", "emph": "em", "textit": "em", "ind": "term", "underline": "em", "footnote": "fn"}


def preprocess(s: str) -> str:
    s = re.sub(r"(?<!\\)%.*", "", s)
    s = strip_command(s, "index")
    for name, tag in FMT.items():
        while True:
            m = re.search(r"\\" + name + r"\s*\{", s)
            if not m:
                break
            e = match_brace(s, m.end() - 1)
            s = s[:m.start()] + f"\x01{tag}\x02" + s[m.end():e] + f"\x01/{tag}\x02" + s[e + 1:]
    s = s.replace("\r", "")
    # \colgur{...} / \colhoy{...} → multicols
    for name, n in (("colgur", 3), ("colhoy", 2)):
        while True:
            m = re.search(r"\\" + name + r"\s*\{", s)
            if not m:
                break
            e = match_brace(s, m.end() - 1)
            s = s[:m.start()] + f"\\begin{{multicols}}{{{n}}}" + s[m.end():e] + "\\end{multicols}" + s[e + 1:]
    s = s.replace("\\z", "$z=x+iy$") if "\\z " in s or "\\z\n" in s else s
    s = re.sub(r"\\hfill\s*\$\\blacksquare\$", "", s)
    s = re.sub(r"\\(chapter)\*?\s*\{", r"\\section{", s) if False else s
    return s


def split_sections(s: str) -> list[tuple[str, str, str]]:
    """\\section, \\subsection-оор хуваана: (level, title, body)."""
    res = []
    pat = re.compile(r"\\(section|subsection|subsubsection)\*?\s*\{")
    pos = 0
    cur = ("intro", "", None)
    starts = []
    for m in pat.finditer(s):
        e = match_brace(s, m.end() - 1)
        starts.append((m.start(), e + 1, m.group(1), s[m.end():e]))
    if not starts:
        return [("intro", "", s)]
    res.append(("intro", "", s[:starts[0][0]]))
    for k, (st, en, lvl, title) in enumerate(starts):
        nxt = starts[k + 1][0] if k + 1 < len(starts) else len(s)
        res.append((lvl, title, s[en:nxt]))
    return res


def clean_title(t: str, ctx: Ctx) -> str:
    t = strip_command(t, "index")
    t = t.replace("\\\\", " ")
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    return inline(t, ctx)


def convert_sections(tex: str, ctx: Ctx, id_prefix: str) -> list[tuple[str, str]]:
    """Хэсгүүдийг [("intro", xml), ("section", xml), ...] болгоно."""
    tex = preprocess(tex)
    parts = split_sections(tex)
    out: list[tuple[str, str]] = []
    # хэсгүүдийг бүлэглэх: section -> [subsections]
    groups = []
    for lvl, title, body in parts:
        if lvl == "intro":
            x = blocks(body, ctx)
            if x.strip():
                out.append(("intro", x))
        elif lvl == "section" or not groups:
            groups.append([title, body, []])
        else:
            groups[-1][2].append((title, body))
    for k, (title, body, subs) in enumerate(groups, 1):
        sid = f"{id_prefix}-s{k}"
        x = f'<section xml:id="{sid}"><title>{clean_title(title, ctx)}</title>'
        b = blocks(body, ctx)
        if subs:
            if b.strip():
                x += f"<introduction>{b}</introduction>"
            for j, (st, sb) in enumerate(subs, 1):
                x += f'<subsection xml:id="{sid}-{j}"><title>{clean_title(st, ctx)}</title>{blocks(sb, ctx) or "<p/>"}</subsection>'
        else:
            x += b or "<p/>"
        x += "</section>"
        out.append(("section", x))
    return out
