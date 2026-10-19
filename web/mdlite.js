/* 轻量 Markdown 阅读渲染（只给“读”用，不改文件）：标题、列表、表格、引用、代码块、加粗/斜体/行内代码、LaTeX 符号。
   book-to-skill 这类工具生成的 skill 里有 $\neg$、$A \rightarrow B$、**加粗**、英文小标题和 YAML 头，直接显示很难读：
   这里把逻辑符号换成 ¬ ∨ ∧ → 等，常见英文小标题换成中文，去掉 YAML 头和 HTML 注释。链接只显示文字，不跳转。 */
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const TEX = {
    neg: "¬", lnot: "¬", land: "∧", wedge: "∧", lor: "∨", vee: "∨", rightarrow: "→", to: "→", Rightarrow: "⇒", implies: "⇒", leftarrow: "←",
    leftrightarrow: "↔", longleftrightarrow: "↔", Leftrightarrow: "⇔", iff: "⇔", equiv: "≡", vdash: "⊢", models: "⊨", cdot: "·", times: "×", div: "÷",
    neq: "≠", ne: "≠", leq: "≤", le: "≤", geq: "≥", ge: "≥", approx: "≈", in: "∈", notin: "∉", subset: "⊂", subseteq: "⊆", supset: "⊃", cap: "∩", cup: "∪",
    forall: "∀", exists: "∃", emptyset: "∅", varnothing: "∅", top: "⊤", bot: "⊥", ldots: "…", dots: "…", cdots: "⋯", pm: "±", infty: "∞",
    alpha: "α", beta: "β", gamma: "γ", delta: "δ", pi: "π", sum: "Σ", therefore: "∴", because: "∵", quad: " ", qquad: "  ", ",": " ", ";": " ", " ": " ",
  };
  const HEAD = {
    "core idea": "核心思想", "frameworks introduced": "引入的框架", "key concepts": "关键概念", "mental models": "思维模型", "anti-patterns": "易错点与反面模式",
    "key takeaways": "要点", "connects to": "与其他章节的联系", "how to use this skill": "怎么用这份心法", "core frameworks & mental models": "核心框架与思维模型",
    "core frameworks": "核心框架", "chapter index": "章节索引", "topic index": "主题索引", "supporting files": "配套文件", "scope & limits": "范围与限制",
    "glossary": "术语表", "patterns": "技巧与模式", "cheatsheet": "速查表", "design patterns": "技巧与模式", "decision guides": "决策指南",
    "key terms": "关键术语", "techniques": "技巧", "examples": "例子", "summary": "小结", "overview": "概览",
  };
  const LABEL = { "Author": "作者", "Pages": "页数", "Chapters": "章数", "Generated": "生成于", "Title": "标题" };

  function tex(s) {
    let t = String(s)
      .replace(/\\text\{([^{}]*)\}/g, "$1").replace(/\\mathrm\{([^{}]*)\}/g, "$1").replace(/\\mathbf\{([^{}]*)\}/g, "$1")
      .replace(/\\([A-Za-z]+|[,; ])/g, (m, k) => (k in TEX ? TEX[k] : k))
      .replace(/(^|[\s(（,，])or(?=[\s)）,，]|$)/g, "$1∨").replace(/(^|[\s(（,，])and(?=[\s)）,，]|$)/g, "$1∧")
      .replace(/(^|[\s(（,，])not(?=[\s)）,，]|$)/g, "$1¬")
      .replace(/[{}]/g, "").replace(/\\\\/g, " ").replace(/\s{2,}/g, " ").trim();
    return t.replace(/¬ (?=[A-Za-z(（¬])/g, "¬");
  }

  // book-to-skill 每份 skill 里固定的英文说明句，换成中文（只在行内文字里换，代码和公式不动）
  const BOILER = [
    [/^\*\*Without arguments\*\* — load core frameworks for reference$/, "**不带问题**——直接加载上面的核心框架，供参考"],
    [/^\*\*With a topic\*\* — ask about (.+?)(?:, or another indexed topic)?; I find and read the relevant chapter$/, "**带主题**——问某个主题（如 $1 等），我会找到并读取对应的章节"],
    [/^\*\*With chapter\*\* — ask for (.+?); I load that specific chapter$/, "**指定章节**——说出章节号（如 $1），我只读取那一章"],
    [/^\*\*Browse\*\* — ask .*to see the full index$/, "**浏览**——想看有哪些章节，问“有哪些章节”即可看到完整目录"],
    [/^When you ask about a topic not covered in Core Frameworks below, I will read the relevant chapter file before answering\.?$/, "如果你问的主题不在下面的核心框架里，我会先读取对应的章节文件再回答。"],
    [/^This skill covers the book content only\..*$/, "这份心法只覆盖原书的内容。要在你自己的做题流程里动手使用，请再配合你自己的评分模板。"],
  ];
  function boiler(t) {
    for (const [re, to] of BOILER) if (re.test(t)) return t.replace(re, to).replace(/` or `/g, "`、`");
    return t.replace(/\bCh\.? ?(\d+)/g, "第$1章").replace(/[（(]\s*(or|and|not)\s*[）)]/g, (_, w) => "（" + { or: "或", and: "且", not: "非" }[w] + "）");
  }

  // 行内：先保护代码，再换公式，再处理加粗/斜体
  function inline(raw) {
    const keep = [];
    const stash = (html) => "\u0000" + (keep.push(html) - 1) + "\u0000";
    let s = boiler(String(raw));
    s = s.replace(/`([^`\n]+)`/g, (_, c) => stash("<code>" + esc(c) + "</code>"));
    s = s.replace(/\$\$([^$]+)\$\$|\$([^$\n]+)\$/g, (_, a, b) => stash('<span class="md-math">' + esc(tex(a ?? b)) + "</span>"));
    s = s.replace(/\[([^\]\n]+)\]\(([^)\n]*)\)/g, (_, t) => t);
    s = esc(s);
    s = s.replace(/\*\*([^*\n]+?)\*\*/g, "<b>$1</b>").replace(/__([^_\n]+?)__/g, "<b>$1</b>")
      .replace(/(^|[^*\w])\*([^*\s][^*\n]*?)\*(?!\*)/g, "$1<i>$2</i>");
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => keep[Number(i)]);
  }

  function headText(t) {
    const plain = t.replace(/\*\*|`/g, "").replace(/\$/g, "").replace(/(?<=[\u4e00-\u9fff）)])\s*[（(][A-Za-z][A-Za-z &-]*[）)]\s*$/, "").trim();
    let m = plain.match(/^Chapter\s+(\d+)\s*[:：-]?\s*(.*)$/i);
    if (m) return `第${m[1]}章${m[2] ? "　" + m[2] : ""}`;
    const k = plain.toLowerCase().replace(/[:：]$/, "");
    if (HEAD[k]) return HEAD[k];
    return plain !== t.replace(/\*\*|`/g, "").replace(/\$/g, "").trim() ? plain : null;
  }

  function render(text) {
    let src = String(text ?? "").replace(/\r\n?/g, "\n");
    src = src.replace(/^---\n[\s\S]*?\n---\n?/, "").replace(/<!--[\s\S]*?-->/g, "");
    const lines = src.split("\n"), out = [];
    let i = 0, list = null;
    const closeList = () => { if (list) { out.push(list.map((l) => l.close).reverse().join("")); list = null; } };
    const para = (t) => out.push(`<p>${inline(t)}</p>`);
    while (i < lines.length) {
      const l = lines[i];
      let m;
      if (/^```/.test(l)) {                                   // 代码块：原样显示
        closeList(); const buf = []; i++;
        while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
        i++; out.push(`<pre class="md-pre">${esc(buf.join("\n"))}</pre>`); continue;
      }
      if ((m = l.match(/^(#{1,6})[ \t]+(.*?)[ \t#]*$/))) {
        closeList();
        const lv = Math.min(m[1].length + 1, 5), tr = headText(m[2]);
        out.push(`<h${lv} class="md-h">${tr ? esc(tr) : inline(m[2])}</h${lv}>`); i++; continue;
      }
      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(l)) { closeList(); out.push("<hr>"); i++; continue; }
      if (/^\s*\|.*\|\s*$/.test(l) && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1] || "") && /-/.test(lines[i + 1] || "")) {   // 表格
        closeList();
        const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const head = cells(l); i += 2; const rows = [];
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
        out.push(`<div class="md-tablewrap"><table class="md-table"><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
        continue;
      }
      if ((m = l.match(/^(\s*)>\s?(.*)$/))) {                 // 引用（连续几行合成一块）
        closeList(); const buf = [m[2]]; i++;
        while (i < lines.length && (m = lines[i].match(/^\s*>\s?(.*)$/))) { buf.push(m[1]); i++; }
        out.push(`<blockquote class="md-quote">${buf.map((b) => (b.trim() ? `<p>${inline(b)}</p>` : "")).join("")}</blockquote>`); continue;
      }
      if ((m = l.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/))) {
        const depth = Math.min(Math.floor(m[1].replace(/\t/g, "  ").length / 2), 3), ordered = /\d/.test(m[2]);
        const tag = ordered ? "ol" : "ul";
        list = list || [];
        while (list.length > depth + 1) out.push(list.pop().close);
        if (list.length < depth + 1 || list[depth].tag !== tag) {
          if (list.length === depth + 1) out.push(list.pop().close);
          while (list.length < depth + 1) { out.push(`<${tag} class="md-list">`); list.push({ tag, close: `</${tag}>` }); }
        }
        out.push(`<li>${inline(m[3])}</li>`); i++; continue;
      }
      if (!l.trim()) { closeList(); i++; continue; }
      closeList();
      const kv = l.match(/^\*\*(Author|Pages|Chapters|Generated|Title)\*\*:\s*(.*)$/);                // book-to-skill 的头部信息行
      if (kv) {
        const parts = l.split("|").map((p) => p.trim()).map((p) => { const x = p.match(/^\*\*([A-Za-z]+)\*\*:?\s*(.*)$/); return x ? `${LABEL[x[1]] || x[1]}：${x[2]}` : p; });
        out.push(`<p class="md-meta">${esc(parts.join("　"))}</p>`); i++; continue;
      }
      const buf = [l.trim()]; i++;                            // 普通段落：连续的非空行合并
      while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|\s*([-*+]|\d+[.)])\s|\s*>|\s*\|)/.test(lines[i]) && !/^\s*([-*_])(\s*\1){2,}\s*$/.test(lines[i])) buf.push(lines[i++].trim());
      para(buf.join(" "));
    }
    closeList();
    return out.join("");
  }

  /** 文件的友好名：book-to-skill 的固定文件名和章节标题换成中文，其余用标题或原文件名 */
  function friendly(rel, title) {
    const base = String(rel).split("/").pop();
    const fixed = { "SKILL.md": "入口", "cheatsheet.md": "速查表", "glossary.md": "术语表", "patterns.md": "技巧库", "变更记录.md": "变更记录" };
    if (fixed[rel] || (fixed[base] && !rel.includes("/"))) return fixed[rel] || fixed[base];
    const t = title ? (headText(title) || title.replace(/\*\*|`|\$/g, "")) : "";
    if (/^ch\d/i.test(base) && t) return t;
    return /[一-鿿]/.test(base) ? base.replace(/\.md$/i, "") : (t || rel);
  }

  window.MDLITE = { render, friendly, tex };
})();
