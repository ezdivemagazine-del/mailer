const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, TableOfContents, HeadingLevel, BorderStyle,
  WidthType, ShadingType, VerticalAlign, PageNumber, PageBreak, Header, Footer,
} = require("docx");

const FONT = "Microsoft JhengHei"; // 微軟正黑體，Windows 通用
const NAVY = "1A1A2E";
const GREEN = "1A6B3C";
const BLUE = "1A4A8C";
const GREY = "666666";
const LIGHT = "F0EFEB";

// ── helpers ──────────────────────────────────────────────────────────────
const P = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: opts.after ?? 120, line: 300, ...(opts.before ? { before: opts.before } : {}) },
    alignment: opts.align,
    children: [new TextRun({ text, bold: opts.bold, italics: opts.italics, color: opts.color, size: opts.size ?? 22 })],
  });

// paragraph with mixed runs
const PR = (runs, opts = {}) =>
  new Paragraph({
    spacing: { after: opts.after ?? 120, line: 300 },
    children: runs.map(r =>
      typeof r === "string"
        ? new TextRun({ text: r, size: 22 })
        : new TextRun({ size: 22, ...r })),
  });

const H1 = (text) =>
  new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 160 }, children: [new TextRun({ text, font: FONT })] });
const H2 = (text) =>
  new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 }, children: [new TextRun({ text, font: FONT })] });

const bullet = (text, level = 0) =>
  new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 60, line: 290 },
    children: [new TextRun({ text, size: 22 })],
  });
const bulletR = (runs, level = 0) =>
  new Paragraph({
    numbering: { reference: "bullets", level },
    spacing: { after: 60, line: 290 },
    children: runs.map(r => typeof r === "string" ? new TextRun({ text: r, size: 22 }) : new TextRun({ size: 22, ...r })),
  });
const numbered = (text) =>
  new Paragraph({
    numbering: { reference: "steps", level: 0 },
    spacing: { after: 60, line: 290 },
    children: [new TextRun({ text, size: 22 })],
  });
const numberedR = (runs) =>
  new Paragraph({
    numbering: { reference: "steps", level: 0 },
    spacing: { after: 60, line: 290 },
    children: runs.map(r => typeof r === "string" ? new TextRun({ text: r, size: 22 }) : new TextRun({ size: 22, ...r })),
  });

// callout box (single-cell shaded table)
const callout = (lines, fill = "FFF8E1", barColor = "F57C00") =>
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 1, color: fill },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: fill },
      right: { style: BorderStyle.SINGLE, size: 1, color: fill },
      left: { style: BorderStyle.SINGLE, size: 24, color: barColor },
    },
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: 9360, type: WidthType.DXA },
            shading: { fill, type: ShadingType.CLEAR },
            margins: { top: 100, bottom: 100, left: 160, right: 140 },
            children: lines.map((ln, i) =>
              new Paragraph({
                spacing: { after: i === lines.length - 1 ? 0 : 60, line: 290 },
                children: (Array.isArray(ln) ? ln : [ln]).map(r =>
                  typeof r === "string" ? new TextRun({ text: r, size: 21 }) : new TextRun({ size: 21, ...r })),
              })),
          }),
        ],
      }),
    ],
    margins: { bottom: 160 },
  });

const spacer = (h = 120) => new Paragraph({ spacing: { after: h }, children: [] });

// data table builder
function makeTable(headers, rows, widths) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      new TableCell({
        width: { size: widths[i], type: WidthType.DXA },
        borders,
        shading: { fill: NAVY, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        verticalAlign: VerticalAlign.CENTER,
        children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, color: "FFFFFF", size: 21 })] })],
      })),
  });
  const bodyRows = rows.map((cells, ri) =>
    new TableRow({
      children: cells.map((c, i) =>
        new TableCell({
          width: { size: widths[i], type: WidthType.DXA },
          borders,
          shading: { fill: ri % 2 ? "F7F6F3" : "FFFFFF", type: ShadingType.CLEAR },
          margins: { top: 70, bottom: 70, left: 120, right: 120 },
          verticalAlign: VerticalAlign.CENTER,
          children: (Array.isArray(c) ? c : [c]).map(line =>
            new Paragraph({ spacing: { line: 280 }, children: [new TextRun({ text: line, size: 21 })] })),
        })),
    }));
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [headerRow, ...bodyRows],
  });
}

// ── content ────────────────────────────────────────────────────────────
const children = [];

// Cover
children.push(
  new Paragraph({ spacing: { before: 2600, after: 0 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "易潛企業開發信系統", bold: true, size: 56, color: NAVY, font: FONT })] }),
  new Paragraph({ spacing: { before: 120, after: 0 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "操作手冊", bold: true, size: 40, color: NAVY, font: FONT })] }),
  new Paragraph({ spacing: { before: 240, after: 0 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "創意種籽 · DRT SHOW · EZDIVE · DIWA · GOGOSCUBA", size: 22, color: GREY })] }),
  new Paragraph({ spacing: { before: 1400, after: 0 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "全公司同仁適用", size: 24, color: NAVY })] }),
  new Paragraph({ spacing: { before: 120, after: 0 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "系統網址（公司內網）：http://192.168.3.200:8000", size: 22, color: GREY })] }),
  new Paragraph({ spacing: { before: 80, after: 0 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "文件版本：2026 年 6 月", size: 20, color: GREY })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// （不放 Word 目錄欄位：匯入企業微信「微文檔」後會失效，改由微文檔自動依標題產生目錄）

// 開始之前
children.push(H1("開始之前"));
children.push(PR([
  "這套系統是公司用來",
  { text: "寫開發信、批量發送行銷郵件", bold: true },
  "的內部平台。不論你在哪個部門，照著這份手冊就能完成寫信、發信與排程。",
]));
children.push(callout([
  [{ text: "重點：", bold: true, color: BLUE }, "系統只能在", { text: "公司內網", bold: true }, "使用。連上公司 Wi-Fi 的手機或筆電都可以開，在家連不到屬正常。"],
  [{ text: "有問題找誰？", bold: true, color: BLUE }, "操作問題找 PM（Tony）；帳號、信箱、技術問題請 IT 協助。"],
], "F0F4FF", BLUE));

// 1 登入
children.push(H1("1. 登入"));
children.push(numbered("用瀏覽器（Chrome、Safari、Edge 皆可）打開 http://192.168.3.200:8000"));
children.push(numbered("輸入帳號與密碼，按「登入」。"));
children.push(numbered("帳號由管理員建立；忘記密碼請找管理員「重設密碼」。"));
children.push(callout([
  [{ text: "登入後系統會記住你", bold: true }, "，下次打開不必重新登入（除非你按了「登出」）。"],
], "E8F5E9", GREEN));

// 2 介面總覽
children.push(H1("2. 介面總覽"));
children.push(P("登入後，最上方有一排功能頁籤："));
children.push(makeTable(
  ["頁籤", "用途", "誰看得到"],
  [
    ["✍️ 寫信", "AI 寫信、編輯、發送", "全部人"],
    ["📬 發送記錄", "查看寄信進度與結果", "全部人"],
    ["🗓 排程", "管理排定好的發送任務", "全部人"],
    ["✒️ 簽名檔", "建立／編輯個人簽名", "全部人"],
    ["⚙️ 信箱", "寄件信箱設定", "全部人可看，僅管理員可新增／刪除"],
    ["👤 帳號", "新增帳號、停用、重設密碼", "僅管理員"],
  ],
  [1700, 4000, 3660],
));
children.push(spacer(80));
children.push(PR([
  "右上角顯示你的帳號名稱、身分（",
  { text: "管理員", bold: true }, " 或 ", { text: "成員", bold: true },
  "）以及「登出」按鈕。",
]));

// 3 寫信
children.push(H1("3. 寫一封信（最常用）"));
children.push(P("點「✍️ 寫信」。畫面分成左右兩半：左邊是設定與 AI 對話，右邊是信件預覽與發送設定。"));

children.push(H2("步驟一：選「發信單位」"));
children.push(P("左上角有 5 個部門按鈕，選哪個部門，AI 就會用那個部門的口吻和立場寫信："));
children.push(makeTable(
  ["部門", "業務角色"],
  [
    ["創意種籽", "國際潛水品牌台灣總代理（Cressi、Seac、Alpha Oceano）"],
    ["DRT SHOW", "亞洲潛水產業展覽平台"],
    ["EZDIVE", "潛水產業媒體與內容平台"],
    ["DIWA", "潛水教育認證機構"],
    ["GOGOSCUBA", "潛水器材與通路平台"],
  ],
  [2200, 7160],
));
children.push(spacer(80));
children.push(callout([
  [{ text: "⚠️ 切換部門會清空目前的對話與信件內容", bold: true, color: "C0392B" }, "，請先確定再切換。"],
]));

children.push(H2("步驟二：選「輸出語言」"));
children.push(PR([
  "可選 ", { text: "繁體中文 / 简体中文 / English", bold: true }, "。",
]));
children.push(callout([
  [{ text: "⚠️ 切換語言同樣會清空目前內容", bold: true, color: "C0392B" }, "，請先選好語言再開始寫。"],
]));

children.push(H2("步驟三：用 AI 寫信"));
children.push(PR([
  "在左下角輸入框打字，按 ", { text: "Enter", bold: true }, " 送出（要換行用 ",
  { text: "Shift + Enter", bold: true }, "）。",
]));
children.push(bulletR([{ text: "第一次：", bold: true }, "描述你要寫什麼，例如「寫一封開發信給潛水店，介紹 Cressi 品牌，強調義大利製造品質」。"]));
children.push(bulletR([{ text: "之後：", bold: true }, "直接用對話方式叫 AI 修改，例如「再正式一點、結尾加上 LINE 聯絡方式」「開頭稱呼改成親愛的店長」「第二段太長了，幫我縮短」。"]));
children.push(P("每次送出後，右邊的「信件預覽」會自動更新（主旨 + 內文）。", { after: 120 }));

children.push(H2("步驟四：手動微調"));
children.push(P("右邊預覽區可以直接編輯："));
children.push(bulletR([{ text: "主旨：", bold: true }, "直接點上面那行字修改。"]));
children.push(bulletR([{ text: "內文：", bold: true }, "用工具列調整粗體／斜體／底線／文字顏色，也可插入連結與圖片。"]));
children.push(bulletR([{ text: "圖片大小：", bold: true }, "插入圖片後，點一下圖片會跳出小視窗，可輸入寬、高（像素）調整。"]));
children.push(P("下方按鈕："));
children.push(bulletR([{ text: "複製全文", bold: true }, "：把主旨＋內文複製起來，可貼到別處。"]));
children.push(bulletR([{ text: "重新開始", bold: true }, "：清空目前這封信，重頭來過。"]));

// 4 收件人
children.push(H1("4. 收件人名單"));
children.push(P("信件產出後，右邊會出現「收件人名單」欄位。"));
children.push(bulletR([{ text: "直接把名單貼進去就好", bold: true }, "，格式不拘：逗號、分號、空格或換行分隔都可以。"]));
children.push(bullet("系統會自動辨識，下方顯示「✓ 已辨識 N 個收件人」，並把每個 email 變成小標籤。"));
children.push(bullet("格式錯的會自動跳過，並提示「跳過 X 個無效」。"));
children.push(bulletR([{ text: "不要的收件人", bold: true }, "，點標籤上的 × 就能移除。"]));

// 5 簽名與信箱
children.push(H1("5. 簽名檔與寄件信箱"));
children.push(P("在信件預覽下方的「發送設定」區："));
children.push(bulletR([{ text: "簽名檔：", bold: true }, "下拉選一個你建好的簽名（或選「不附加簽名檔」）。選了之後預覽下方會用虛線隔出簽名內容。建立簽名見第 10 節。"]));
children.push(bulletR([{ text: "寄件信箱：", bold: true }, "下拉選一個要用來寄信的信箱。你能選的，是管理員授權給你的那些；若是空的，請見第 11、12 節。"]));

// 6 發送方式
children.push(H1("6. 發送方式與發送節奏"));
children.push(H2("發送方式（兩種）"));
children.push(makeTable(
  ["方式", "說明", "什麼時候用"],
  [
    ["每人一封", "每位收件人各自收到一封獨立的信，彼此看不到別人", "開發信、正式商務信（最常用、推薦）"],
    ["密件副本 BCC", "一次把所有人放進密件副本寄出", "同一份通知大量發送"],
  ],
  [1900, 4000, 3460],
));
children.push(spacer(80));
children.push(callout([
  [{ text: "兩種方式收件人都看不到彼此的 email。", bold: true }, "差別在「每人一封」更像一對一，BCC 是一次群發。"],
], "E8F5E9", GREEN));

children.push(H2("發送節奏（避免被信箱服務商擋信）"));
children.push(bulletR([{ text: "每人一封 模式：", bold: true }, "設定「每 ___ 分鐘寄 ___ 封」。例：每 5 分鐘寄 20 封，系統會慢慢分批寄。"]));
children.push(bulletR([{ text: "BCC 模式：", bold: true }, "設定「每批 ___ 位，每批間隔 ___ 分鐘」。"]));
children.push(callout([
  [{ text: "💡 建議不要把速度設太快。", bold: true }, "量大時放慢節奏，能降低被 Gmail／企業信箱判定為垃圾信的風險。"],
], "F0F4FF", BLUE));

// 7 立即 vs 排程
children.push(H1("7. 立即發送 vs. 排程發送"));
children.push(P("設定都完成後，下方有兩顆按鈕："));
children.push(H2("立即發送（綠色）"));
children.push(P("按下後立刻在背景開始寄信。"));
children.push(callout([
  [{ text: "✅ 關掉瀏覽器、關電腦都不影響", bold: true, color: GREEN }, "，信會繼續在伺服器上寄。進度去「📬 發送記錄」看。"],
], "E8F5E9", GREEN));
children.push(H2("排程發送（藍色）"));
children.push(P("按下後展開一個小表單："));
children.push(numbered("填排程名稱（例：六月開發信）。"));
children.push(numbered("選發送時間（台灣時間）。"));
children.push(numbered("按「確認存入排程」。"));
children.push(P("到了設定的時間，系統會自動發送。排程可以事後修改或取消，見第 9 節。"));
children.push(callout([
  [{ text: "發送按鈕變灰色不能按", bold: true }, "，通常是因為：還沒產生信件、沒選收件人、或沒選寄件信箱。"],
]));

// 8 發送記錄
children.push(H1("8. 發送記錄"));
children.push(P("點「📬 發送記錄」，可看到每一次發送任務：主旨、發送方式、建立時間、進度條與統計（總計／已寄／失敗）。"));
children.push(P("狀態標籤："));
children.push(bulletR([{ text: "待處理", bold: true, color: "F57C00" }, " — 排隊中"]));
children.push(bulletR([{ text: "進行中", bold: true, color: "1565C0" }, " — 正在寄（可按「取消」中止）"]));
children.push(bulletR([{ text: "已完成", bold: true, color: GREEN }]));
children.push(bulletR([{ text: "失敗", bold: true, color: "C0392B" }]));
children.push(bulletR([{ text: "已取消", bold: true, color: GREY }]));
children.push(P("點「重新整理」更新最新進度。", { after: 120 }));
children.push(callout([
  [{ text: "成員只看得到自己的記錄；", bold: true }, "管理員看得到全部人的記錄（每筆會標示是誰寄的）。"],
], "F0F4FF", BLUE));

// 9 排程管理
children.push(H1("9. 排程管理"));
children.push(P("點「🗓 排程」，可看到所有排定的發送任務。"));
children.push(bullet("上方可用「全部／待發／已發／已取消」篩選。"));
children.push(bullet("每筆顯示名稱、主旨、發送時間、狀態。"));
children.push(bulletR([{ text: "待發的排程可以：", bold: true }, "編輯（名稱、時間、主旨、內文、收件人、寄件信箱、發送方式）或取消。"]));
children.push(bulletR([{ text: "任何排程", bold: true }, "都可以刪除。"]));
children.push(callout([
  [{ text: "新增排程", bold: true }, "要去「✍️ 寫信」頁面寫好信後按「🗓 排程發送」，這頁只負責管理已存在的排程。"],
]));

// 10 簽名檔
children.push(H1("10. 簽名檔管理"));
children.push(callout([
  [{ text: "📌 寄信前請先設定好你自己的簽名檔。", bold: true, color: "C0392B" }, "簽名是個人的，每位同事第一次使用前都要先建立一次，之後寫信就能直接套用。"],
], "FFF8E1", "F57C00"));
children.push(P("點「✒️ 簽名檔」。每個人可以建立多個自己的簽名。"));
children.push(numbered("按右上角「＋ 新增簽名」。"));
children.push(numbered("填簽名名稱（例：Tony · 業務總監）。"));
children.push(numbered("在編輯器裡編排內容，支援文字、粗體、顏色、連結、圖片。"));
children.push(numbered("可勾選「設為預設簽名」（會標 ★，寫信時優先選用）。"));
children.push(numbered("按「建立簽名」。"));
children.push(P("清單上每個簽名都能編輯或刪除，下方會顯示預覽。"));
children.push(callout([
  [{ text: "簽名是個人的", bold: true }, "，只有你自己看得到、用得到。"],
], "E8F5E9", GREEN));

// 11 信箱設定
children.push(H1("11. 信箱設定"));
children.push(callout([
  [{ text: "📌 同事請注意：", bold: true, color: "C0392B" }, "新增寄件信箱需要用到第三方信箱的密碼（Gmail 應用程式密碼、企業信箱授權碼等），請", { text: "直接找 Tony 協助設定", bold: true }, "，不要自行嘗試。"],
], "FFF8E1", "F57C00"));
children.push(P("點「⚙️ 信箱」。所有人都看得到已設定的信箱，但只有管理員能新增或刪除。以下流程供管理員 / Tony 參考。"));
children.push(H2("新增寄件信箱"));
children.push(numberedR([{ text: "快速套用", bold: true }, "可一鍵帶入常見設定：Gmail / 阿里企業信箱 / 阿里雲 DirectMail。"]));
children.push(numberedR([{ text: "填入帳號、密碼等資訊。", bold: true }, "Gmail：主機 smtp.gmail.com、埠號 465，密碼要用「應用程式密碼」（不是登入密碼）。"]));
children.push(numberedR([{ text: "按「測試連線並新增」。", bold: true }, "系統會先測試能不能寄信，成功才會存。"]));
children.push(callout([
  [{ text: "設好之後", bold: true }, "，要記得到「👤 帳號」把這個信箱授權給需要用的成員（見第 12 節）。"],
  [{ text: "註：", bold: true }, "阿里雲 DirectMail 目前在 NAS 上暫時停用，請以 SMTP（Gmail／企業信箱）為主。"],
]));

// 12 帳號管理
children.push(H1("12. （管理員）帳號管理"));
children.push(P("點「👤 帳號」（只有管理員看得到）。"));
children.push(H2("新增帳號"));
children.push(numbered("填帳號名稱（小寫英文或數字）、初始密碼（至少 6 字元）。"));
children.push(numberedR([{ text: "選角色：", bold: true }, "成員（一般使用者）或管理員（可管理信箱與帳號）。"]));
children.push(numbered("按「建立帳號」。"));
children.push(H2("管理現有帳號"));
children.push(bulletR([{ text: "啟用 / 停用", bold: true }, " — 員工離職就停用（admin 帳號不能停用）。"]));
children.push(bulletR([{ text: "重設密碼", bold: true }, " — 員工忘記密碼時用，輸入新密碼即可。"]));
children.push(bulletR([{ text: "信箱權限（僅對成員）", bold: true }, " — 勾選要授權給這位成員使用哪些寄件信箱。"]));
children.push(callout([
  [{ text: "成員只能用被授權的信箱寄信", bold: true }, "，所以新成員建立後記得設定信箱權限。"],
]));

// 13 FAQ
children.push(H1("13. 常見問題 FAQ"));
const faqs = [
  ["打不開系統？", "確認你連在公司內網（公司 Wi-Fi 或辦公室網路）。網址是 http://192.168.3.200:8000。在家連不到屬正常。"],
  ["忘記密碼怎麼辦？", "找管理員（或 Tony）用「帳號管理 → 重設密碼」幫你設一組新密碼。"],
  ["寄件信箱下拉是空的？", "表示還沒有信箱授權給你。請管理員到「帳號管理 → 信箱權限」勾選授權。"],
  ["發送按鈕是灰色按不了？", "檢查是否：① 已產生信件、② 至少有 1 個有效收件人、③ 已選寄件信箱。三項都齊全才會亮起。"],
  ["按了「立即發送」後可以關電腦嗎？", "可以。寄信在伺服器背景進行，關瀏覽器、關電腦都不影響。進度去「發送記錄」看。"],
  ["信被退回或進垃圾信匣？", "① 把發送節奏放慢（量大時尤其重要）；② 內容避免過多連結與敏感字眼；③ 確認寄件信箱的網域設定正常（找 IT）。"],
  ["切換部門或語言後，剛寫的信不見了？", "這是正常設計——切換會清空內容重來。請先選好部門和語言再開始寫，或寫完一封寄完再切換。"],
  ["AI 寫得不滿意？", "直接在對話框告訴它怎麼改（更正式、更短、換開頭、加聯絡方式…），它會即時改寫，不用整封重寫。"],
];
faqs.forEach(([q, a]) => {
  children.push(PR([{ text: "Q：" + q, bold: true, color: NAVY }], { after: 40 }));
  children.push(PR([{ text: "A：", bold: true }, a], { after: 160 }));
});

children.push(spacer(200));
children.push(new Paragraph({
  spacing: { before: 200 }, alignment: AlignmentType.CENTER,
  border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC", space: 8 } },
  children: [new TextRun({ text: "如系統有更新，請以實際畫面為準，並通知 PM 更新本手冊。", italics: true, size: 20, color: GREY })],
}));

// ── document ──────────────────────────────────────────────────────────
const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONT, color: NAVY },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: NAVY, space: 4 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 25, bold: true, font: FONT, color: BLUE },
        paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 540, hanging: 280 } } } },
      ] },
      { reference: "steps", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 540, hanging: 320 } } } },
      ] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "易潛企業開發信系統 · 操作手冊　　", size: 18, color: GREY }),
            new TextRun({ children: [PageNumber.CURRENT], size: 18, color: GREY }),
          ],
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("易潛企業開發信系統-操作手冊.docx", buf);
  console.log("done");
});
