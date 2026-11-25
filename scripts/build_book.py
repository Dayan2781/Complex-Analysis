#!/usr/bin/env python3
"""Эх LaTeX лекцүүдээс (latex/lectures/) PreTeXt бүлгүүдийг (source/chapters/lec-XX.ptx) үүсгэх.

НЭГ УДААГИЙН ШИЛЖҮҮЛЭГ. Үүсгэсэн .ptx файлуудыг цаашид шууд засна;
энэ скриптийг дахин ажиллуулбал lec-XX.ptx файлууд дарагдана.
AI, семинар, гэрийн даалгаврын файлууд (ai-XX, sem-XX, hw-XX) ба гараар
бичсэн хэсгүүд (extra-*.ptx) хөндөгдөхгүй.

    python3 scripts/build_book.py
"""
from __future__ import annotations

import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from tex2ptx import Ctx, convert_sections, resolve_refs  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEX = ROOT / "latex" / "lectures"
OUT = ROOT / "source" / "chapters"
IMG_SRC = ROOT / "latex" / "Zurag"
IMG_DST = ROOT / "source" / "external" / "images"
END = 10**6

# Эх файлд олдсон алдааны засвар: (файл, хуучин, шинэ)
FIXES = [
    ("6resdue.tex", r"\sin t=\frac{e^{it}-e^{-it}}{2}$$", r"\sin t=\frac{e^{it}-e^{-it}}{2i}$$"),
    ("6resdue.tex", r"\frac{1}{2}\left[z-\frac{1}{z}\right]", r"\frac{1}{2i}\left[z-\frac{1}{z}\right]"),
    ("6resdue.tex", r"\item[III.]\textbf{Жорданы лемм.}", r"\item[III.]\textbf{Жорданы леммийн мөрдлөгөө.} (Лемм нь <<Жорданы лемм>> хэсэгт.)"),
    ("2complex function.tex",
     r"цэгийн аливаа орчинд $\mathbb{C}$ (буюу  $\overline{\mathbb{C}}$)-ийн топологи утгаар $\{a_n\}$ дарааллын төгсгөлгүй олон элемент оршиж байвал уул дарааллыг $a$-хязгаартай гэж нэрлэнэ. $\{a_n\}$ дараалал $\mathbb{C}$-д цор ганц хязгаарын $a$ цэгтэй байвал $a$-руу нийллээ гэх бөгөөд",
     r"цэгийн аливаа орчинд $\{a_n\}$ дарааллын \textbf{төгсгөлөг тооноос бусад бүх} гишүүн оршиж байвал (өөрөөр хэлбэл $\forall\varepsilon>0$ $\exists N$: $n>N\Rightarrow |a_n-a|<\varepsilon$; $a=\infty$ үед $|a_n|>1/\varepsilon$) дараалал $a$-руу нийлнэ гэх бөгөөд"),
    ("2complex function.tex", r"дугуй оршин байвал түүнийг компакт муж", r"дугуй оршин байвал түүнийг зааглагдсан муж"),
    ("5integral.tex", r"$D\subset \mathbb{C}$ компакт муж ба", r"$D\subset \mathbb{C}$ зааглагдсан муж ба"),
    ("5integral.tex", r"\textbf{(Интеграл орших зайлшгүй нөхцөл.)}", r"\textbf{(Интеграл орших хүрэлцээтэй нөхцөл.)}"),
    ("5integral.tex", r"$f$ нь $D$ мужид $n$ удаа дифференциалчлагддаг байг.", r"$f\in H(D)$ ба $\gamma^+$ нь Кошийн интеграл томьёоны нөхцөлийг хангах зам байг."),
    ("4differential.tex", r"Голоморф $w=f(z)$, $f(z_0)\ne 0$ функцээр", r"Голоморф $w=f(z)$, $f'(z_0)\ne 0$ функцээр"),
    ("4differential.tex", r"iv (z,y)", r"iv (x,y)"),
    ("5series.tex", r"$$f(z)=\sum\limits_{n=0}^\infty c_n(z-z_0)$$", r"$$f(z)=\sum\limits_{n=0}^\infty c_n(z-z_0)^n$$"),
    ("5series.tex", r"|c_n (z_0-a)|\leq M", r"|c_n (z_0-a)^n|\leq M"),
    ("8.tex", r"Теорем 9.1-ийн нөхцөлд", r"өмнөх теоремын нөхцөлд"),
]

EULER_FIX = r"""
\section{Комплекс экспонент ба Эйлерийн томьёо}
\begin{dfn}
$z=x+iy$ тооны хувьд \emph{комплекс экспонентыг}
$$e^{z}=e^{x}(\cos y+i\sin y)$$
гэж тодорхойлно. Бодит $z=x$ үед энэ нь ердийн $e^x$ болно, мөн $e^{z_1+z_2}=e^{z_1}e^{z_2}$ (тригонометрийн нэмэх томьёогоор шалгана).
\end{dfn}
\begin{thm}[Эйлерийн томьёо]
Аливаа бодит $\varphi$-ийн хувьд
\begin{equation}\label{eulereq1}
    \cos\varphi+i\sin\varphi=e^{i\varphi}.
\end{equation}
\end{thm}
\begin{prf}
Тодорхойлолтод $x=0$, $y=\varphi$ гэж орлуулахад шууд гарна. (Хожим 11-р лекцэд $e^z=\sum z^n/n!$ цувааг ашиглан мөн адил дүгнэлтэд хүрнэ.)
\end{prf}
"""

# Бүлэг бүрийн гарчиг ба эх сурвалжийн хэсгүүд: (файл, эхний мөр, сүүлийн мөр)
CHAPTERS = [
    (1, "Комплекс тоо ба комплекс хавтгай", [("1complex numbers.tex", 2, 161), ("1complex numbers.tex", 178, 293)]),
    (2, "Комплекс хавтгайн топологи. Риманы бөмбөлөг", [("2complex function.tex", 55, 184), ("2complex function.tex", 257, 376)]),
    (3, "Комплекс функц, хязгаар ба тасралтгүй чанар", [("lec 3 by Mimi.tex", 3, 439)]),
    (4, "Элементар функцүүд ба олон утгат функц", [("@EULER", 0, 0), ("2complex function.tex", 21, 54), ("3holomorphic function.tex", 81, 209), ("lec 3 by Mimi.tex", 440, 499)]),
    (5, "Комплекс уламжлал. Коши–Риманы нөхцөл", [("4differential.tex", 2, 155)]),
    (6, "Голоморф ба гармоник функц. Конформ буулгалт", [("4differential.tex", 156, 326)]),
    (7, "Бутархай шугаман ба элементар функцийн буулгалт", [("7linear and other.tex", 2, 604)]),
    (8, "Комплекс интеграл", [("5integral.tex", 2, 125)]),
    (9, "Кошийн интеграл теорем. Эх функц", [("5integral.tex", 126, 324)]),
    (10, "Кошийн интеграл томьёо ба түүний мөрдлөгөө", [("5integral.tex", 325, 395)]),
    (11, "Цуваа. Тейлорын цуваа", [("5series.tex", 2, 591)]),
    (12, "Лораны цуваа ба тусгаарлагдсан онцгой цэг", [("6resdue.tex", 3, 291)]),
    (13, "Үлдэцийн онол", [("6resdue.tex", 292, 415)]),
    (14, "Үлдэцийн теоремын хэрэглээ", [("6resdue.tex", 416, 548)]),
    (15, "Аналитик үргэлжлэл ба Риманы зета функц", [("7linear and other.tex", 753, 822)]),
    (16, "Геометр зарчмууд", [("8.tex", 1, 111), ("8.tex", 120, 166)]),
]
APPENDIX = [
    ("app-products", "Төгсгөлгүй үржвэр ба мероморф функц", [("7linear and other.tex", 621, 728), ("7linear and other.tex", 737, 752)]),
    ("app-elliptic", "Эллипслэг функц", [("8.tex", 167, 179)]),
    ("app-laplace", "Үйлдлийн тооллын үндэс (Лапласын хувиргалт)", [("9.tex", 3, 251)]),
]
# Гараар бичсэн нэмэлт хэсгүүд (бүлгийн лекцийн хэсгүүдийн дараа орно)
EXTRA = {
    14: ["extra-14-jordan.ptx"],
    15: ["extra-15-zeta.ptx"],
}
# Аналитик үргэлжлэлийн бүлэгт эх лекцийн хэсгүүд гараар бичсэн зета хэсгээс ӨМНӨ орно.


def read_lines(fname: str) -> list[str]:
    text = (TEX / fname).read_text(encoding="utf-8")
    for f, old, new in FIXES:
        if f == fname:
            if old not in text:
                print(f"АНХААР: засвар олдсонгүй [{fname}]: {old[:60]}")
            text = text.replace(old, new)
    key = re.sub(r"[^A-Za-z0-9]", "", fname.split(".")[0])[:6] or "f"
    text = re.sub(r"\\(label|ref)\{([^}]*)\}", lambda m: f"\\{m.group(1)}{{{key}:{m.group(2)}}}", text)
    return text.split("\n")


def gather(segments) -> str:
    out = []
    for fname, a, b in segments:
        if fname == "@EULER":
            out.append(EULER_FIX)
            continue
        lines = read_lines(fname)
        out.append("\n".join(lines[a - 1:min(b, len(lines))]))
    return "\n\n".join(out)


def chapter_xml(cid: str, title: str, parts, includes: list[str], tag: str = "chapter") -> str:
    intro = "".join(x for k, x in parts if k == "intro")
    secs = "".join(x for k, x in parts if k == "section")
    inc = "".join(f'\n  <xi:include href="./{h}" />' for h in includes)
    body = f'<{tag} xml:id="{cid}" xmlns:xi="http://www.w3.org/2001/XInclude">\n  <title>{title}</title>\n'
    if intro:
        body += f"  <introduction>{intro}</introduction>\n"
    body += secs + inc + f"\n</{tag}>\n"
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    IMG_DST.mkdir(parents=True, exist_ok=True)
    all_ids: dict[str, str] = {}
    images: set[str] = set()
    pending = []
    for n, title, segs in CHAPTERS:
        ctx = Ctx("r", images)
        parts = convert_sections(gather(segs), ctx, f"lec{n:02d}")
        all_ids.update(ctx.kinds)
        inc = EXTRA.get(n, []) + [f"ai-{n:02d}.ptx", f"sem-{n:02d}.ptx", f"hw-{n:02d}.ptx"]
        pending.append((OUT / f"lec-{n:02d}.ptx", chapter_xml(f"ch{n:02d}", title, parts, inc)))
    for aid, title, segs in APPENDIX:
        ctx = Ctx("r", images)
        parts = convert_sections(gather(segs), ctx, aid)
        all_ids.update(ctx.kinds)
        pending.append((OUT / f"{aid}.ptx", chapter_xml(aid, title, parts, [], tag="appendix")))
    for path, xml in pending:
        path.write_text(resolve_refs(xml, all_ids), encoding="utf-8")
        print("бичлээ", path.relative_to(ROOT))
    for name in sorted(images):
        src = IMG_SRC / name
        if src.exists():
            shutil.copy(src, IMG_DST / name)
        else:
            print("зураг олдсонгүй:", name)


if __name__ == "__main__":
    main()
