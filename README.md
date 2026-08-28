# xetex-stack-renderer

`xetex-stack-renderer` 是一個 XeTeX/XeLaTeX 的 Unicode-driven stack rendering
framework。正文只需直接輸入 Unicode；frontend 會按已註冊的 Unicode range 找出完整
script run，再把整個 run 交給 backend。Egyptian Hieroglyphs 是第一個 backend，目前
只輸出可觀察的 stub，尚未實作 EHFC/Hieropy layout。

```tex
\usepackage{xetex-stack-renderer}
```

## 分層

- `tex/xetex-stack-renderer.sty`：LaTeX frontend、選項與 backend 載入。
- `tex/xsr-core.sty`：XeTeX range/class registry、active run collector、dispatch，
  以及 external renderer/cache bridge。
- `tex/xsr-egyptian.sty`：Egyptian ranges 與 TeX-side backend handler。
- `src/xsr/registry.py`：Python-side generic Unicode run detection。
- `src/xsr/renderer.py`、`cache.py`：backend protocol、CLI 與 content-addressed cache。
- `src/xsr/egyptian/backend.py`：Egyptian placeholder backend。

預設 `mode=auto`：若已有預處理 response 就直接讀取；否則在 unrestricted
`shell-escape` 下呼叫 Python；兩者皆不可用時顯示 TeX stub。因此文件本身仍只需要
一行 `\usepackage{xetex-stack-renderer}`。

## 安裝與測試

先安裝 Python package，再讓 TeX 找到 `tex/`（正式安裝時也可把三個 `.sty` 複製到
個人 TEXMF tree）：

```powershell
python -m pip install -e .
$env:TEXINPUTS = "$PWD\tex;$env:TEXINPUTS"
python -m pytest
xelatex -shell-escape examples/minimal.tex
```

不使用 `shell-escape` 時，可先產生 response；`auto` mode 會讀取它們：

```powershell
python -m xsr.renderer preprocess --input examples/minimal.tex --output-dir .
xelatex examples/minimal.tex
```

## 當前限制

- Egyptian backend 只證明完整 run 已成功 dispatch；尚無 EHFC、Hieropy、字形定位或
  真正的 stack layout。
- TeX frontend 會把已註冊 range 設為 active collectors；若其他 package 重新定義同一
  range 的 catcode 或 active character meaning，兩者目前尚無協調機制。
- 最小 preprocessor 以 Unicode ranges 掃描原始 `.tex`，尚不理解 TeX comments、macro
  expansion 或 `\input` 圖；manifest 已保留來源 hash，後續可據此加入嚴格驗證。
