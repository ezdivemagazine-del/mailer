# IT 部門設定說明 — 易潛企業開發信系統

> 此文件提供 IT 人員在系統正式使用前須完成的設定項目。
> 完成後請告知 PM，系統才能正式上線。

---

## 一、DNS 網域驗證（必做，否則信件會進垃圾匣）

### 為什麼要做？

Email 伺服器會驗證「這封信真的是從這個網域發出的嗎？」  
若沒有以下設定，收件方的郵件伺服器很可能直接把信件判定為垃圾郵件。

### 需要新增的 DNS 記錄

請在公司網域（例如 `yichian.com`）的 DNS 管理後台新增以下記錄：

---

#### 1. SPF 記錄（說明誰可以代表此網域發信）

| 類型 | 名稱 | 值 |
|------|------|----|
| TXT | `@`（或 `yichian.com`） | `v=spf1 include:spf.qiye.aliyun.com include:_spf.google.com ~all` |

> ⚠️ 若已有 SPF 記錄，不可新增第二條，需把 `include:` 合併進現有記錄。

---

#### 2. DKIM 記錄（數位簽章，防偽造）

**阿里企業信箱：**  
登入阿里企業郵件後台 → 郵件安全 → DKIM，按指示取得 DKIM 公鑰，在 DNS 新增：

| 類型 | 名稱 | 值 |
|------|------|----|
| TXT | `mail._domainkey.yichian.com` | （從後台複製）|

**阿里雲 DirectMail（如有使用）：**  
登入 DirectMail 控制台 → 發信域名 → 驗證，按頁面指示新增 DNS 記錄（通常包含 DKIM + SPF + MX 追蹤域）。

---

#### 3. DMARC 記錄（選做，提升信任度）

| 類型 | 名稱 | 值 |
|------|------|----|
| TXT | `_dmarc.yichian.com` | `v=DMARC1; p=none; rua=mailto:postmaster@yichian.com` |

> `p=none` 代表只監控不阻擋，上線初期建議使用。

---

### DNS 生效時間

DNS 更改通常需要 **30 分鐘到 24 小時**才會全球生效。  
可用以下工具驗證：[https://mxtoolbox.com/spf.aspx](https://mxtoolbox.com/spf.aspx)

---

## 二、阿里企業信箱 SMTP 開通（如使用 alimail）

1. 登入企業郵件後台（管理員）
2. 前往「設定 → 安全設定 → 客戶端專用密碼」
3. 為業務帳號開通「POP3/SMTP/IMAP 服務」
4. 產生「客戶端專用密碼」（非登入密碼）
5. 將此密碼交給 PM 填入系統信箱設定

---

## 三、阿里雲 DirectMail 開通（批量發信用）

> 推薦用於每次發送超過 100 封的場景，避免企業信箱信譽受損。

1. 登入阿里雲控制台 → 搜尋「郵件推送 DirectMail」→ 開通服務
2. **發信域名驗證**：新增子域名（例如 `mail.yichian.com`），按指示完成 DNS 驗證
3. **建立發信地址**：例如 `no-reply@mail.yichian.com`
4. **建立 RAM 子帳號**：
   - 控制台 → RAM 訪問控制 → 用戶 → 新建
   - 賦予權限：`AliyunDirectMailFullAccess`
   - 建立 AccessKey，取得 AccessKey ID 與 Secret
5. 將 AccessKey ID / Secret 交給 PM 填入系統

---

## 四、QNAP NAS 網路設定

系統僅供內網使用，確認以下事項：

- [ ] NAS 的 IP 在公司內網固定（建議設靜態 IP，例如 `192.168.1.100`）
- [ ] 防火牆允許公司電腦存取 NAS 的 `8000` 埠
- [ ] 若需要從外部存取（非首版需求），需設定 VPN 或反向代理，**不建議直接對外開放 8000 埠**

---

## 五、確認清單

完成後請逐項確認：

- [ ] SPF 記錄已新增並生效
- [ ] DKIM 記錄已新增並生效
- [ ] 阿里企業信箱客戶端密碼已產生並交付 PM
- [ ] DirectMail 發信域名已驗證（若使用）
- [ ] DirectMail AccessKey 已建立並交付 PM（若使用）
- [ ] NAS 靜態 IP 已設定
- [ ] 內網防火牆埠號 8000 已開通

---

_如有問題請聯絡 PM 或直接在 Claude Code 中詢問。_
