# SmartApply - Web Agent for Internship Auto-Application

A modular web automation agent built with **browser-use**, **Gemini 2.0 Flash** (via langchain-google-genai), and **FastAPI**. Designed for headless operation on OCI Ubuntu VMs.

## 🚀 Features

- **AI-Powered Web Automation**: Uses Gemini 2.0 Flash for intelligent task execution
- **Headless Browser**: Runs Playwright Chromium without GUI (server-ready)
- **REST API**: FastAPI endpoints for triggering agent tasks
- **Modular Architecture**: Clean separation of concerns for easy maintenance

## 📁 Project Structure

```
SmartApply---Internship-Auto-Applier/
├── app/                          # Application package
│   ├── __init__.py              # Package initializer
│   ├── main.py                  # FastAPI application entry point
│   ├── config.py                # Configuration management
│   └── agent/                   # Agent module
│       ├── __init__.py          # Agent exports
│       └── web_agent.py         # browser-use + Gemini integration
├── requirements.txt             # Python dependencies
├── setup.sh                     # OCI VM setup script
├── .env.template                # Environment variables template
├── .gitignore                   # Git ignore rules
└── README.md                    # This file
```

## 🛠️ Setup (OCI Ubuntu VM)

### Quick Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/SmartApply---Internship-Auto-Applier.git
   cd SmartApply---Internship-Auto-Applier
   ```

2. **Run the setup script**:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Configure environment**:
   ```bash
   # Edit .env with your API key
   nano .env
   ```

4. **Start the server**:
   ```bash
   source venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

### Manual Setup

If you prefer manual installation:

```bash
# 1. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright browsers
playwright install chromium --with-deps

# 4. Configure environment
cp .env.template .env
# Edit .env with your GOOGLE_API_KEY

# 5. Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 🔑 Configuration

Copy `.env.template` to `.env` and set your values:

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_API_KEY` | Your Gemini API key | ✅ Yes |
| `APP_ENV` | Environment (development/production) | No |
| `HOST` | Server host (default: 0.0.0.0) | No |
| `PORT` | Server port (default: 8000) | No |
| `HEADLESS` | Run browser headless (default: true) | No |

Get your API key at: https://aistudio.google.com/app/apikey

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI documentation |
| POST | `/agent/run` | Execute a web agent task |

### Example: Run Agent Task

```bash
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Go to google.com and search for Python tutorials"}'
```

Response:
```json
{
  "success": true,
  "task": "Go to google.com and search for Python tutorials",
  "result": "Successfully searched for Python tutorials..."
}
```

## 🧪 Development

```bash
# Run with auto-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run directly
python -m app.main
```

## 📝 License

MIT License - feel free to use and modify.
