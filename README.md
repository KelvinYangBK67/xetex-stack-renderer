# xetex-stack-renderer

`xetex-stack-renderer` 是 XeTeX/XeLaTeX 的 Unicode-driven stack rendering framework。使用者只需載入套件，正文直接輸入 Unicode；standalone detector 會找出完整 script run，再交給已註冊的 backend。

```tex
\usepackage{xetex-stack-renderer}
```

Egyptian Hieroglyphs 是第一個 backend。目前已經透過 Hieropy 解析 Unicode/EHFC run，但輸出仍是可觀察 dispatch 成功的 stub，尚未實作 glyph layout。

## 架構

- `tex/xetex-stack-renderer.sty`：零 markup 的 LaTeX frontend，組合 detector 與 backend。
- `tex/xsr-core.sty`：通用 backend registry、完整 run dispatch API、外部 renderer 與 response interface；不負責偵測，也不寫死 Egyptian 邏輯。
- `tex/xsr-detector-active.sty`：standalone active-character detector。未來的 host/template 可不載入此模組，直接呼叫 `\xsr_dispatch_run:nn`。
- `tex/xsr-egyptian.sty`：註冊 Egyptian ranges、backend version 與 TeX-side handler。
- `src/xsr/registry.py`：Python-side script/range registry 與完整 Unicode run detection。
- `src/xsr/renderer.py`、`cache.py`：CLI、外部 renderer protocol、預處理模式與 content-addressed cache。
- `src/xsr/egyptian/hieropy_adapter.py`：隔離 Hieropy API，將 Unicode/EHFC run 解析成不透明的中間結果，並把 parser error 轉成 `EgyptianParseError`。
- `src/xsr/egyptian/backend.py`：先解析完整 run，再產生 stub TeX response。

每個 external-renderer request 的 identity 綁定 script、Unicode codepoints、backend version 與 renderer options。TeX response 以 request digest 命名，因此同一 run 編號的內容改變時不會誤讀舊 response。

## 安裝與測試

```powershell
python -m pip install -e .
$env:TEXINPUTS = "$PWD\tex;$env:TEXINPUTS"
python -m pytest -q
xelatex -shell-escape examples/minimal.tex
```

預處理模式可先產生 content-addressed response，再於禁用 shell escape 時編譯：

```powershell
python -m xsr.renderer preprocess --input examples/minimal.tex --output-dir .
xelatex examples/minimal.tex
```

## 當前限制

- Egyptian backend 只驗證完整 run 能由 Hieropy 成功解析；尚未實作 glyph positioning、boxes、scaling、overlay、mirror 或 damage rendering。
- standalone detector 仍會將已註冊 range 設為 active；需要避免此全局字符行為的 host 應只載入 core/backend，並自行提交完整 run。
- 最小 preprocessor 只掃描原始 `.tex` 的 Unicode ranges，不理解 macro expansion、`\input` 或完整 TeX 語法。
- 不支援 HieroTeX compatibility。
