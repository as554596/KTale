# KTale

<p align="center">
  <a href="#繁體中文">繁體中文</a> ・ <a href="#english">English</a>
</p>

<a id="繁體中文"></a>
<details open>
<summary><b>🇹🇼 繁體中文</b>（點擊收合 / 展開）</summary>

一個可以在手機瀏覽器上使用的 AI 韓中小說翻譯工具。後端跑在你自己的電腦（或伺服器）上，前端是純網頁，透過同一個區域網路（或部署到雲端後透過網址）用手機存取。

支援 EPUB / TXT 上傳、AI 術語表提取、AI 術語校對（含繁簡體統一）、批次翻譯、漏翻校對。

---

## 功能

- **文件上傳**：EPUB / TXT，可批量處理
- **術語提取**：用 LLM 從原文中抓出人名、地名、專有名詞，並自動判斷人名性別
- **術語校對**：AI 複審術語翻譯的一致性，輸出可選擇統一為繁體中文或簡體中文
- **批次翻譯**：帶術語表替換、並發控制、失敗自動保留原文
- **漏翻校對**：翻譯完成後檢查是否有段落沒翻好
- **自訂 Prompt**：提取 / 校對 / 翻譯三個階段都可以自訂提示詞
- **本地儲存**：API Key 和設置只存在你瀏覽器的 localStorage，不會上傳到任何第三方

## 技術架構

- 後端：Python + Flask (`backend/app_new.py`)，呼叫任何 OpenAI 相容的 API（DeepSeek、OpenAI 等）
- 前端：純 HTML/CSS/JS (`frontend/index_final.html` + `frontend/app_final.js`)，沒有打包工具，直接由 Flask 靜態伺服

---

## 快速開始（本機 / 區域網路）

### 1. 安裝需求

- Python 3.9+（開發時用的是 3.14，但 3.9 以上應該都可以）
- 一個 OpenAI 相容的 API Key（推薦 [DeepSeek](https://platform.deepseek.com/)，中文效果好且便宜）

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 啟動後端

```bash
cd backend
python app_new.py
```

看到以下訊息就代表啟動成功：

```
Server starting...
Access at: http://localhost:5000
```

Windows 也可以直接雙擊根目錄的 `run_backend.bat`。

### 4. 在電腦上打開

瀏覽器輸入：`http://localhost:5000`

### 5. 在手機上打開

手機和電腦要連**同一個 WiFi**。

在電腦上執行 `ipconfig`（Windows）或 `ifconfig` / `ip addr`（Mac/Linux）查看區域網路 IP（例如 `192.168.1.100`），然後在手機瀏覽器輸入：

```
http://<你電腦的區域網路IP>:5000
```

可以用「加到主畫面」讓它看起來像原生 App。

### 6. 設置 API Key

打開「設置」頁面，分別填入：
- **術語提取 API**：API Key / 端點 / 模型
- **術語校對 API**：API Key / 端點 / 模型 / 輸出語言（繁體 / 簡體）/ 小說背景設定 / 自訂提示詞
- **翻譯 API**：API Key / 端點 / 模型 / 並發數 / 批次大小

三組可以填同一個 Key，也可以分開用不同帳號（例如翻譯量大時分流）。

**這些設置只存在你瀏覽器的 localStorage，後端不會落地保存，也不會傳給除了你指定的 API 端點以外的任何地方。**

### 7. 使用流程

```
上傳文件 → 提取術語表 → 校對術語表（可選）→ 開始翻譯 → 下載結果 → （可選）漏翻校對
```

---

## 部署到伺服器（讓外部也能連）

如果你想脫離「同一個 WiFi」的限制，讓自己或朋友從外部連線，有以下幾種常見做法：

### 選項 A：雲端主機（VPS）長期跑

1. 把整個專案上傳到你的 VPS（GitHub clone 或直接傳檔案）
2. 安裝依賴：`pip install -r requirements.txt`
3. 用 `gunicorn` 或 `waitress` 等生產級 WSGI Server 取代 Flask 內建的開發伺服器（`app.run()` 那行有 debug 模式，正式環境不要用）：
   ```bash
   pip install gunicorn
   cd backend
   gunicorn -w 4 -b 0.0.0.0:5000 app_new:app
   ```
4. 設置防火牆只開放你需要的 port，並考慮在前面加 Nginx + HTTPS（Let's Encrypt）
5. **重要**：這個專案目前沒有登入驗證機制，任何知道網址的人都能用你伺服器的資源呼叫 AI API。如果要公開部署，建議至少加一層 Basic Auth 或者只在自己知道的路徑 / 加白名單 IP。

### 選項 B：內網穿透（不用租伺服器，適合臨時用）

在你電腦本機啟動後端後，用以下工具之一把 `localhost:5000` 暴露到公網：

- [ngrok](https://ngrok.com/)：`ngrok http 5000`
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/)：`cloudflared tunnel --url http://localhost:5000`

拿到的網址在你電腦開著、隧道沒斷的情況下，任何裝置都能連。免費版網址通常每次重啟會變。

### 關於 API Key 安全

- 前端只把 API Key 存在使用者自己瀏覽器的 localStorage，每次呼叫時才連同請求送到你的後端，再由後端轉發給 AI 供應商
- 後端**不會**把 API Key 寫入任何 log 檔或資料庫
- 如果你要把這個專案的程式碼推上 GitHub，`.gitignore` 已經排除了 `.env`、任何 log 檔、暫存輸出檔；**上傳前務必自己確認沒有把真實 Key 寫死在程式碼裡**（可以搜尋一下 `sk-` 開頭的字串）
- 不要把你自己的 `.env`（如果建立了的話）提交到版本控制，只提交 `.env.example` 這個範本

---

## 專案結構

```
mobile_novel_translator/
├── backend/                        # Flask 後端
│   ├── app_new.py                  # 主程式（實際使用的版本）
│   ├── _paths.py                   # 讓子資料夾模組可用扁平 import 互相引用
│   ├── epub/                       # EPUB 解析與翻譯
│   │   ├── enhanced_epub_parser.py
│   │   └── translator.py
│   ├── txt/                        # TXT 翻譯
│   │   ├── txt_translator.py
│   │   └── smart_translator_txt.py
│   ├── glossary/                   # 術語提取與校對
│   │   ├── glossary_extractor_llm.py
│   │   ├── glossary_reviewer.py
│   │   └── glossary_review_engine.py
│   ├── quality/                    # 翻譯質量檢測、自適應分塊
│   │   ├── quality_checker.py
│   │   ├── smart_translator.py
│   │   └── adaptive_chunker.py
│   ├── language/                   # 繁簡體轉換
│   │   └── traditional_converter.py
│   ├── utils/                      # 檔案上傳處理
│   │   └── upload_handler.py
│   └── tests/                      # 開發過程留下的測試腳本
├── frontend/
│   ├── index_final.html            # 主頁面（實際使用的版本）
│   ├── app_final.js                # 主邏輯
│   └── quality_checker.html/js     # 漏翻校對頁面
├── requirements.txt
├── run_backend.bat                 # Windows 一鍵啟動
└── .env.example                    # 環境變數範本（不含真實 Key）
```

---

## 故障排除

**手機打不開**
- 確認手機和電腦連同一個 WiFi
- 電腦防火牆可能擋掉區域網路連入，先在電腦瀏覽器測試 `http://<你的IP>:5000` 能不能打開
- 電腦重開機或重連 WiFi 後 IP 可能會變，記得重新查一次

**提取 / 校對卡在某個百分比不動**
- 目前沒有內建的 API 逾時重試機制，如果卡住通常是 API 那邊回應很慢或掛了，等待或換一個模型 / 端點試試

**翻譯後有些段落沒翻到**
- 用「漏翻校對」頁面（翻譯完成後點擊「前往漏翻校對」）逐段檢查並重翻

---

## 授權

MIT License

</details>

<a id="english"></a>
<details>
<summary><b>🇬🇧 English</b> (click to expand)</summary>

A mobile-friendly AI tool for translating Korean novels into Chinese. The backend runs on your own computer (or a server); the frontend is a plain web page you open on your phone over the same WiFi (or over the internet once deployed).

Supports EPUB / TXT upload, AI glossary extraction, AI glossary review (with Traditional/Simplified Chinese unification), batch translation, and a missed-translation checker.

---

## Features

- **File upload**: EPUB / TXT, batch upload supported
- **Glossary extraction**: an LLM extracts character names, place names, and proper nouns from the source text, including automatic gender inference for character names
- **Glossary review**: an AI pass reviews translation consistency; output can be unified to either Traditional or Simplified Chinese
- **Batch translation**: glossary-aware translation with concurrency control; failed segments fall back to the original text instead of breaking the run
- **Missed-translation check**: after translation, review any low-confidence or untranslated paragraphs
- **Custom prompts**: extraction, review, and translation each accept a custom prompt
- **Local-only storage**: your API keys and settings live only in your browser's localStorage and are never sent anywhere except the API endpoint you configure

## Tech Stack

- Backend: Python + Flask (`backend/app_new.py`), calls any OpenAI-compatible API (DeepSeek, OpenAI, etc.)
- Frontend: plain HTML/CSS/JS (`frontend/index_final.html` + `frontend/app_final.js`), no build step, served directly as static files by Flask

---

## Quick Start (Local / LAN)

### 1. Requirements

- Python 3.9+ (developed on 3.14, but 3.9+ should work)
- An OpenAI-compatible API key ([DeepSeek](https://platform.deepseek.com/) is recommended: strong Chinese output, low cost)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the backend

```bash
cd backend
python app_new.py
```

You'll know it's running when you see:

```
Server starting...
Access at: http://localhost:5000
```

On Windows you can also just double-click `run_backend.bat` in the project root.

### 4. Open on your computer

Open in a browser: `http://localhost:5000`

### 5. Open on your phone

Your phone and computer must be on **the same WiFi network**.

Run `ipconfig` (Windows) or `ifconfig` / `ip addr` (Mac/Linux) on your computer to find its LAN IP (e.g. `192.168.1.100`), then open on your phone:

```
http://<your computer's LAN IP>:5000
```

You can "Add to Home Screen" so it behaves like a native app.

### 6. Configure API keys

Open the "Settings" page and fill in:
- **Glossary extraction API**: API key / endpoint / model
- **Glossary review API**: API key / endpoint / model / output language (Traditional/Simplified) / novel background / custom prompt
- **Translation API**: API key / endpoint / model / concurrency / batch size

You can use the same key for all three, or split them across different accounts (e.g. to spread out usage on high-volume translation).

**These settings live only in your browser's localStorage. The backend does not persist them to disk, and they are never sent anywhere except the API endpoint you configured.**

### 7. Workflow

```
Upload → Extract glossary → Review glossary (optional) → Translate → Download → Check for missed translations (optional)
```

---

## Deploying to a Server (for access beyond your LAN)

If you want to go beyond "same WiFi" and let yourself or friends connect from outside, here are the common options:

### Option A: Run on a VPS long-term

1. Upload the project to your VPS (`git clone` or copy the files directly)
2. Install dependencies: `pip install -r requirements.txt`
3. Replace Flask's built-in dev server with a production WSGI server such as `gunicorn` or `waitress` (the `app.run()` call has `debug=True`, which should never be used in production):
   ```bash
   pip install gunicorn
   cd backend
   gunicorn -w 4 -b 0.0.0.0:5000 app_new:app
   ```
4. Lock down the firewall to only the port you need, and consider putting Nginx + HTTPS (Let's Encrypt) in front of it
5. **Important**: This project currently has **no authentication**. Anyone who knows the URL can use your server's resources to call the AI API on your behalf. If you deploy it publicly, add at least Basic Auth, or restrict access to an IP allowlist / an unguessable path.

### Option B: Tunneling (no server rental, good for temporary use)

After starting the backend locally, expose `localhost:5000` to the internet with one of:

- [ngrok](https://ngrok.com/): `ngrok http 5000`
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/): `cloudflared tunnel --url http://localhost:5000`

The resulting URL is reachable from any device as long as your computer stays on and the tunnel stays connected. Free-tier URLs usually change every time you restart.

### About API key security

- The frontend only stores the API key in the user's own browser localStorage; it's sent to your backend with each request and forwarded to the AI provider from there
- The backend **never** writes the API key to any log file or database
- If you push this project to GitHub, `.gitignore` already excludes `.env`, log files, and generated output; **before pushing, double-check you haven't hardcoded a real key anywhere** (search for strings starting with `sk-`)
- Never commit your own `.env` file (if you create one) — only `.env.example` (the template) should be committed

---

## Project Structure

```
mobile_novel_translator/
├── backend/                        # Flask backend
│   ├── app_new.py                  # main entry point (the version actually in use)
│   ├── _paths.py                   # lets submodules import each other by plain name
│   ├── epub/                       # EPUB parsing and translation
│   │   ├── enhanced_epub_parser.py
│   │   └── translator.py
│   ├── txt/                        # TXT translation
│   │   ├── txt_translator.py
│   │   └── smart_translator_txt.py
│   ├── glossary/                   # glossary extraction and review
│   │   ├── glossary_extractor_llm.py
│   │   ├── glossary_reviewer.py
│   │   └── glossary_review_engine.py
│   ├── quality/                    # translation quality checks, adaptive chunking
│   │   ├── quality_checker.py
│   │   ├── smart_translator.py
│   │   └── adaptive_chunker.py
│   ├── language/                   # Traditional/Simplified conversion
│   │   └── traditional_converter.py
│   ├── utils/                      # file upload handling
│   │   └── upload_handler.py
│   └── tests/                      # leftover test scripts from development
├── frontend/
│   ├── index_final.html            # main page (the version actually in use)
│   ├── app_final.js                # main logic
│   └── quality_checker.html/js     # missed-translation check page
├── requirements.txt
├── run_backend.bat                 # one-click launcher for Windows
└── .env.example                    # env var template (no real keys)
```

---

## Troubleshooting

**Can't open on phone**
- Make sure your phone and computer are on the same WiFi
- Your computer's firewall may be blocking LAN connections — first test `http://<your-ip>:5000` in a browser on the computer itself
- The IP may change after a reboot or WiFi reconnect — check it again

**Extraction or review progress gets stuck**
- There's currently no built-in timeout/retry logic — if it's stuck, the API is likely slow or unresponsive; wait it out or try a different model/endpoint

**Some paragraphs weren't translated**
- Use the "missed-translation check" page (click "Go to missed-translation check" after translation finishes) to review and retranslate paragraph by paragraph

---

## License

MIT License

</details>
