# xetex-stack-renderer

`xetex-stack-renderer` 是 XeTeX/XeLaTeX 的 Unicode-driven stack rendering framework。使用者只需載入套件，正文直接輸入 Unicode；standalone detector 會找出完整 script run，再交給已註冊的 backend。

```tex
\usepackage{xetex-stack-renderer}
```

Egyptian Hieroglyphs 是第一個 backend。目前已透過 Hieropy 0.1.4 解析 Unicode/EHFC run，並能把單一 sign、horizontal joiner、vertical joiner及其 H/V nesting 輸出成真正的 XeTeX glyph boxes。glyph 由 XeTeX 當前字體排出，不會 rasterize 或嵌入外部圖片。

## 架構

- `tex/xetex-stack-renderer.sty`：零 markup 的 LaTeX frontend，組合 detector 與 backend。
- `tex/xsr-core.sty`：通用 backend registry、完整 run dispatch API、外部 renderer 與 response interface；不負責偵測，也不寫死 Egyptian 邏輯。
- `tex/xsr-detector-active.sty`：standalone active-character detector。未來的 host/template 可不載入此模組，直接呼叫 `\xsr_dispatch_run:nn`。
- `tex/xsr-egyptian.sty`：註冊 Egyptian ranges、backend version 與 TeX-side handler。
- `src/xsr/registry.py`：Python-side script/range registry 與完整 Unicode run detection。
- `src/xsr/renderer.py`、`cache.py`：CLI、外部 renderer protocol、預處理模式與 content-addressed cache。
- `src/xsr/egyptian/hieropy_adapter.py`：隔離 Hieropy API，將 Unicode/EHFC run 解析成不透明的中間結果，並把 parser error 轉成 `EgyptianParseError`。
- `src/xsr/egyptian/layout.py`：唯一接觸 Hieropy layout internals 的邊界，將完成 fit/format 的 H/V tree 轉成 XSR geometry。
- `src/xsr/egyptian/model.py`：XSR-owned `RenderResult` / `GlyphPlacement`，使用 em-based、top-origin 座標。
- `src/xsr/egyptian/backend.py`：將 geometry 序列化成 XeTeX box/placement commands。

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

- Egyptian layout 目前只支援 plain signs、U+13431 horizontal joiner、U+13430 vertical joiner與 nested H/V groups。
- insertion、overlay、enclosure/cartouche、mirror、damage/shading、rotation與其他進階 EHFC controls 會明確報錯，不會靜默 fallback。
- Hieropy 0.1.4 的 `Literal.size()` 會用其 bundled NewGardiner measurement font 計算 geometry；XSR 只讀取該 geometry，真正 glyph 仍來自當前 XeTeX font。字體比例差異可能需要後續 tuning。
- layout box 使用 Hieropy top-left coordinates，x 向右、y 向下；目前 baseline 固定在 canvas bottom，尚未做進階 typographic baseline tuning。
- 文件當前使用的字體必須包含 Egyptian Hieroglyphs。測試明確選用 Hieropy bundled NewGardiner，但 generic core/backend 不會選定任何字體。
- standalone detector 仍會將已註冊 range 設為 active；需要避免此全局字符行為的 host 應只載入 core/backend，並自行提交完整 run。
- 最小 preprocessor 只掃描原始 `.tex` 的 Unicode ranges，不理解 macro expansion、`\input` 或完整 TeX 語法。
- 不支援 HieroTeX compatibility。
