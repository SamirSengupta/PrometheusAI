
# PrometheusAI – Local LLM Chatbot with Web Search & OCR Document Upload

A fully-offline-capable Flask application that turns any LM Studio model into a web-chat assistant.  
Ask questions, upload PDFs/images (OCR), and get real-time web answers – all through a clean browser UI.

## What it is

A self-hosted chat interface that wires a local LLM (LM Studio) to web search + document OCR, so you can talk to your files and the internet without sending data anywhere.

## Features

| Feature | Works offline? | Notes |
|---------|----------------|-------|
| Local LLM chat | ✅ | Uses LM Studio API (localhost:1200) |
| Web search | ❌ | Brave, Bing, Google fallbacks |
| PDF text extraction | ✅ | PyPDF2 first, OCR fallback |
| Image OCR | ✅ | Tesseract |
| Anonymous chats | ✅ | RAM only |
| Persistent chats | ✅ | JSON file per user |
| Streaming replies | ✅ | Server-sent events |
| Google login | ✅ | Optional (for chat history) |

## Quick-start (Windows / macOS / Linux)

### 1. Install prerequisites

```bash
# Python 3.9+
python --version

# LM Studio
# Download https://lmstudio.ai → start it → load any model → leave server running on localhost:1200
```

### 2. Clone / unzip this project

```bash
cd PrometheusAI
```

### 3. Create & activate virtual environment

```bash
# macOS/Linux
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 5. (Optional) Install OCR

- **Windows**: `choco install tesseract` or download installer
- **macOS**: `brew install tesseract`
- **Linux**: `sudo apt install tesseract-ocr poppler-utils`

### 6. Run

```bash
python app.py
```

Visit **http://localhost:5000**

Health check: **http://localhost:5000/health**

## Folder & File Map

```
PrometheusAI/
├── app.py                  # Main Flask server
├── requirements.txt        # Python packages
├── chat_sessions.json      # Created automatically (persisted chats)
├── uploads/                # Temporary file cache (auto-cleaned)
└── templates/
    └── index.html          # Single-page chat UI
```

## Environment Variables (all optional)

| Var | Default | Purpose |
|-----|---------|---------|
| `LM_STUDIO_URL` | `http://localhost:1200/v1/chat/completions` | Local LLM endpoint |
| `MODEL_NAME` | `ibm/granite-4-h-tiny` | Fallback model tag |
| `PORT` | `5000` | Flask port |
| `DEBUG` | `True` | Flask debug/reload |
| `SECRET_KEY` | `your-secret-key-change-in-production` | Session crypto |

## How to Use

### Chat

Open **http://localhost:5000** → type → Enter.  
First visit is anonymous; click "Login with Google" (optional) to save history.

### Upload a Document

Click the paper-clip icon → choose PDF / JPG / PNG / GIF / BMP.  
Text appears in the chat box automatically; ask questions about it.

### Force Web Search

Prefix any message with "latest", "current", "today", "news", etc.  
The bot will scrape top 2 Brave/Bing results and cite URLs.

### Streaming vs Non-Streaming

- **Normal**: `/api/chat` → full response at once
- **Streaming**: `/api/chat/stream` → typewriter effect (used by UI)

## API Examples

```bash
# Health
curl http://localhost:5000/health

# Direct web search
curl -X POST http://localhost:5000/api/web-search \
     -H "Content-Type: application/json" \
     -d '{"query":"local llm vs openai","num_results":3}'

# Chat (non-stream)
curl -X POST http://localhost:5000/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message":"What is the date today?"}'
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Could not connect to LM Studio" | Start LM Studio → load a model → enable local server on port 1200 |
| OCR errors | Install Tesseract + Poppler (Windows: add folder to PATH) |
| Port 5000 in use | `set PORT=5001 && python app.py` |
| Huge PDF hangs | Set `max_pages=3` in `DocumentProcessor.ocr_pdf()` |

## Security Notes

- No data leaves your machine except for web-search GET requests.
- Anonymous chats live only in RAM.
- Uploaded files are deleted immediately after OCR.
- Change `SECRET_KEY` before any public deployment.

## License

MIT – do what you want, no warranty.

---

**Local LLMs for everyone** 🚀
