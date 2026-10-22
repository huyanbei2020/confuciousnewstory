# confuciousnewstory · 论语新说

沿用 Carrot 水墨山水、宣纸色与宋体阅读风格的古籍书房，部署于 GitHub Pages。

## 资料

| 书名 | 本地来源 | 阅读范围 |
| --- | --- | --- |
| 论语义疏 | 本地专项分层对校稿 | 十卷及卷首 |
| 四书章句集注 | 本地保存的殆知阁电子录文 | 大学、中庸、论语、孟子及附录 |
| 朱子语类 | 本地 Word 全文整理稿 | 一百四十卷 |
| 论孟精义 | 本地保存的殆知阁电子录文 | 论语二十卷、孟子十四卷及序 |
| 论语正义 | 本地东里书斋电子录文连续整理稿 | 二十四卷、凡例、郑玄序逸文及刘恭冕后叙 |

`sources/manifest.json` 记录源文件相对路径、整理状态与 SHA-256。`sources/` 保留原始导入文件；`docs/texts/` 提供逐字相同的下载副本。正文保留原字，仍须校勘，不是校定本。

功能：卷目阅读、每页 35 段、字号调整、跨五书简繁检索、匹配高亮和段落定位、手动选卷双栏对读、本机书签、引文复制及全文下载。没有后端或运行时密钥。检索在 Web Worker 中完成，第一次检索下载五书数据，后续复用内存缓存。

## 本地运行

```sh
python3 scripts/build.py
python3 -m http.server 8765 --bind 127.0.0.1 --directory docs
```

打开 http://127.0.0.1:8765/ 。不要直接以 `file://` 打开，因为数据通过 fetch 加载。

```sh
python3 -m unittest discover -s tests
node --check docs/assets/app.js
node --test tests/search.mjs
```

Node 测试要求 Node 22 或更新版本；构建只需 Python 标准库。

## GitHub Pages

仓库 Settings → Pages → Source 选 **GitHub Actions**。推送 main 后，`.github/workflows/pages.yml` 自动构建、核验并部署 `docs/`。页面所有资源均使用相对路径，hash 路由支持项目子路径，无需自定义域名或服务端。

目标地址（仓库名统一为小写后）：https://huyanbei2020.github.io/confuciousnewstory/

## 整理规则

- 原始下载不变，阅读视图移除 Word 页码域、重复卷尾题与电子分类标签；《论语正义》另移除来源网页的字数、更新时间与前后篇导航。
- 长段仅为显示拆分，每个分段保留原文。段号供本站定位，不是影印本页码。
- 经、注、疏标签来自已有整理稿；自动分层不等同于底本核定。
- 检索做常用简繁字形归一并忽略标点，不改写阅读文本。
- 《四书章句集注》按现有卷目保留四书全本，未把《论语集注》冒充全书。
- 《论孟精义》保留孟子十四卷，未用只有论语部分的另一文件替代。

## 设计与资源来源

样式、江南水墨背景、宣纸纹理、字体来自用户指定的 Carrot 本地项目。原 Carrot 项目已拉取并合并远端更新，保留原有本地校读提交。未拷贝其密钥、后端、问答接口或其他文献数据。

字体许可见 `docs/assets/fonts/LICENSE.noto`；OpenCC 字形映射许可及来源见 `docs/assets/vendor/`。古籍录文的具体底本与待校状态见网站“资料说明”。

## 识典参照初校（2026-10-22）

尚未完成五部书的逐句校定。`collation/report.html` 是全库导入原稿的检查报告；`issues.csv` 和每书的 `*-audit.json` 保留段号、缺字、层次疑点、对齐结果及参照链接。未对齐不等于原文错误，可能来自版本、分段或参照缺页。

本轮只对《论孟精义》逐字归一对齐、署名明确的解说及另行核对的两段经文补标点、标层次，保存于 `sources/editorial.json`。所有原字和原始下载保留；构建时检查修改前哈希。阅读页逐段链接识典，并注明初校。《朱子语类》原来的“经文／引经”提示改为“语录 · 引文（待核）”，避免把语录中的引文误作独立经文。

《论语义疏》识典参照为大阪怀德堂纪念会本，与本地四库系统整理稿底本不同，且参照 OCR 有明显讹误；不可整体替换。《论语正义》尚未找到刘宝楠、刘恭冕本的独立识典书页，未用其他同名或近名书替代。其他书的经注分界、异文、缺字及未对齐段落仍待逐项核对。

复核工具（仅读取公开章页，不使用登录或私有接口）：

```sh
python3 scripts/collation/fetch_shidian.py
python3 scripts/collation/audit.py
python3 scripts/collation/prepare_corrections.py
python3 scripts/build.py
python3 -m unittest discover -s tests
```

公开参照缓存放在忽略目录 `.local/shidian/reference/`，包含抓取时间和页面哈希。覆盖率及缺页原因写入报告；页面内容或目录更新后，重新读取的结果可能不同。`prepare_corrections.py` 只是保守的初校辅助，不能证明识典的标点正确。
