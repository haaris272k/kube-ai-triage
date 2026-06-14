# Kubernetes AI Troubleshooter

**AI-powered incident triage for Kubernetes** - Automatically collects pod signals (status, logs, events, describe) and generates intelligent root cause analysis with remediation recommendations.

Built with Python, Gemini AI, and Kubernetes Python Client.

## Features

✅ **Automated Signal Collection**
- Pod status and health checks
- Container logs (last N lines, configurable)
- Kubernetes events (warnings, errors)
- Pod describe information
- Multi-container support

✅ **AI-Powered Analysis**
- Root cause identification using Gemini AI
- Confidence scoring (HIGH/MEDIUM/LOW)
- Evidence-based reasoning
- Actionable remediation steps

✅ **Beautiful CLI Output**
- Rich terminal UI with colors and tables
- Progress indicators
- Markdown and JSON output formats
- Save reports to files

✅ **Production-Ready**
- Structured logging (console + file)
- Simple typed Python modules using plain dictionaries
- Cost-controlled (configurable log limits)
- Error handling and validation

## Quick Start

### 1. Prerequisites

- Python 3.10+
- kubectl configured with cluster access
- Gemini API key ([Get one here](https://aistudio.google.com/app/apikey))

### 2. Installation

```bash
# Navigate to the project directory
cd k8s-ai-troubleshooter

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -e .
```

### 3. Configuration

**⚠️ Important:** Add your Gemini API key to `.env`:

```bash
# Edit the .env file
nano .env

# Update this line with your actual API key:
GEMINI_API_KEY="your-actual-gemini-api-key-here"
```

### 4. Usage

**Analyze a pod:**

```bash
k8s-triage pod springpm-api-dev-ga-6468d85b66-frhrz
```

**With custom namespace:**

```bash
k8s-triage pod my-pod -n production
```

**Save report to file:**

```bash
k8s-triage pod my-pod --save report.md
```

**Full options:**

```bash
k8s-triage --help
```

## How It Works

```
┌─────────────────────────────────────────────────┐
│  1. Collect K8s Signals                         │
│     ✓ Pod status, events, logs, describe        │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│  2. Analyze with Gemini AI                      │
│     ✓ Root cause + confidence + evidence        │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│  3. Generate Beautiful Report                   │
│     ✓ Terminal output OR save to file           │
└─────────────────────────────────────────────────┘
```

## Example Output

```
╭───────────────────────────────────────────────╮
│   Kubernetes Incident Triage Report          │
╰───────────────────────────────────────────────╯

Service Information
Pod         springpm-api-dev-ga-6468d85b66-frhrz
Namespace   skydeck-dev
Status      Running
Ready       1/1

╭─────────── Root Cause Analysis ────────────╮
│ Confidence: HIGH                            │
│                                             │
│ Root Cause:                                 │
│ Application experiencing high memory usage  │
╰─────────────────────────────────────────────╯

Supporting Evidence:
  1. Pod restarted 3 times in last hour
  2. Last event: "OOMKilled"
  3. Logs show: "OutOfMemoryError"

Remediation Recommendations:
  1. Increase memory limits to 1Gi
  2. Review application memory profiling
  3. Add memory usage alerts
```

## Project Structure

```
k8s-ai-troubleshooter/
├── k8s_ai_triage/
│   ├── __init__.py             # Package metadata
│   ├── cli.py                  # CLI entrypoint
│   ├── config.py               # Configuration
│   ├── logger.py               # Logging
│   ├── kubernetes_collector.py # Kubernetes signal collection
│   ├── incident_analyzer.py    # Gemini AI analysis
│   └── incident_reporter.py    # Terminal and file reporting
├── .env.example                # Safe configuration template
├── requirements.txt            # Python dependencies
├── setup.py                    # Package installation metadata
├── PROJECT_DOCUMENTATION.md    # Architecture and interview guide
└── logs/                       # Local application logs, ignored by git
```

## Troubleshooting

### "Cannot connect to Kubernetes cluster"
- Ensure `kubectl` is configured: `kubectl get pods`
- Check namespace: `kubectl get pods -n skydeck-dev`

### "Cannot initialize Gemini client"
- Check your API key in `.env`
- Verify key is valid at https://aistudio.google.com/

### "Pod not found"
- Verify pod exists: `kubectl get pods -n skydeck-dev`

## Author

**Haaris**  
SRE Engineer | AI/ML Enthusiast  
Built as a portfolio project demonstrating production-grade operational automation.

---

**Status:** ✅ End-to-end implementation complete!
