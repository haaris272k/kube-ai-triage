# K8s AI Triage - Complete Project Documentation

### What is K8s AI Triage?

K8s AI Triage is an **AI-powered Kubernetes incident response tool** that automates the initial troubleshooting phase of production incidents. It acts as a "first responder" SRE, collecting cluster signals and generating intelligent root cause analysis with remediation recommendations.

### Problem Statement

**Traditional Kubernetes Troubleshooting:**
- SREs manually run multiple kubectl commands: `get pod`, `describe pod`, `logs`, `get events`
- Time-consuming during high-pressure incidents (P0/P1)
- Requires deep K8s expertise to correlate signals
- Inconsistent analysis quality depending on SRE experience
- No structured documentation of initial findings

**Our Solution:**
- **Automated signal collection** from Kubernetes API
- **AI-powered analysis** using Google Gemini to correlate signals
- **Instant insights** with confidence scoring and evidence
- **Actionable remediation** steps, not just diagnosis
- **Shareable reports** in markdown/JSON format

### Value Proposition

**For SREs:**
- Reduces MTTD (Mean Time To Detect) by providing instant analysis
- Serves as a "second pair of eyes" during incidents
- Captures institutional knowledge via AI training
- Generates documentation automatically

**For Organizations:**
- Faster incident response (minutes instead of hours)
- Consistent troubleshooting quality across team
- Reduced reliance on senior SRE availability
- Cost optimization via intelligent log sampling

### Key Features

**Automated Data Collection**
- Pod status, health, and lifecycle information
- Container states, restart counts, exit codes
- Kubernetes events (warnings, errors)
- Container logs with intelligent truncation
- Multi-container pod support

**AI-Powered Analysis**
- Root cause identification with confidence scoring
- Evidence-based reasoning (references specific signals)
- Pattern recognition across logs, events, conditions
- Context-aware recommendations

**Production-Ready Design**
- Cost controls (configurable log limits)
- Error handling and graceful degradation
- Structured logging for audit trails
- Type-safe implementation
- Clean, maintainable codebase (~1200 lines)

**User Experience**
- Beautiful CLI with Rich terminal formatting
- Progress indicators during analysis
- Color-coded status and confidence levels
- Multiple output formats (markdown, JSON)
- Report export for sharing

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User (SRE/DevOps)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CLI Layer (cli.py)                            │
│  - Click framework for argument parsing                         │
│  - Rich library for terminal UI                                 │
│  - Progress indicators and error handling                       │
│  - Orchestrates: collect → analyze → report                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Collector  │    │   Analyzer   │    │   Reporter   │
│              │    │              │    │              │
│ Kubernetes   │───▶│   Gemini     │───▶│   Rich UI    │
│ Python       │    │   AI API     │    │   Markdown   │
│ Client       │    │              │    │   JSON       │
└──────┬───────┘    └──────┬───────┘    └──────────────┘
       │                   │
       ▼                   ▼
┌──────────────┐    ┌──────────────┐
│  Kubernetes  │    │   Google     │
│   Cluster    │    │   Gemini     │
│  (via API)   │    │     API      │
└──────────────┘    └──────────────┘
```

### Data Flow

```
1. User Input: k8s-triage pod my-app-xyz -n production

2. Signal Collection (KubernetesCollector):
   ├─ Pod Status      → {phase, ready, restarts, age, node}
   ├─ Conditions      → [{type, status, reason, message}, ...]
   ├─ Container Stats → [{name, state, restart_count}, ...]
   ├─ Events          → [{type, reason, message, count}, ...]
   ├─ Logs            → [{container, logs, line_count}, ...]
   └─ Describe        → {raw_output, events, conditions}
   
   Output: signals_dict (nested Python dict)

3. AI Analysis (IncidentAnalyzer):
   ├─ Build Prompt    → Structured JSON format for Gemini
   ├─ Call Gemini API → model: gemini-2.0-flash-exp, temp: 0.1
   ├─ Parse Response  → Extract root cause, confidence, evidence
   └─ Validate        → Ensure required fields present
   
   Output: analysis_dict {root_cause, confidence, evidence, recommendations}

4. Report Generation (IncidentReporter):
   ├─ Format Data     → Rich terminal UI with colors, tables
   ├─ Display Report  → Console output with panels, syntax highlighting
   └─ Optional Save   → Markdown file or JSON export
   
   Output: Formatted report displayed in terminal
```

### Module Breakdown

#### 1. **cli.py** - Command-Line Interface (246 lines)
**Purpose:** Main entry point, orchestrates the entire pipeline

**Key Components:**
- `cli()` - Main Click group with global options
- `pod()` - Pod analysis command (primary use case)
- `deployment()` - Future: multi-pod analysis
- `version()` - Display version info

**Dependencies:**
- Click: Argument parsing, command routing
- Rich: Terminal UI (Progress, Panel, Console)
- All other modules: Collector, Analyzer, Reporter

**Responsibilities:**
- Parse command-line arguments
- Validate configuration (API key check)
- Setup logging
- Execute analysis pipeline with progress indicators
- Handle errors gracefully with user-friendly messages
- Display results and optionally save to file

#### 2. **kubernetes_collector.py** - K8s Signal Collection (379 lines)
**Purpose:** Collect comprehensive troubleshooting data from Kubernetes cluster

**Key Components:**
- `KubernetesCollector` class
  - `collect_pod_status()` - Pod phase, readiness, restarts
  - `collect_pod_events()` - Recent events with filtering
  - `collect_pod_logs()` - Container logs with truncation
  - `collect_pod_describe()` - Describe-like summary
  - `collect_all_signals()` - Orchestrator method

**Dependencies:**
- kubernetes: Official Kubernetes Python client
- config: For namespace, context settings

**Design Highlights:**
- Uses K8s Python client (not kubectl subprocess)
- Returns plain dicts (not Pydantic models) for simplicity
- Cost-aware: Limits log lines (default: 200) to control LLM tokens
- Graceful degradation: Missing logs return empty, not crash

#### 3. **incident_analyzer.py** - AI Analysis Engine (194 lines)
**Purpose:** Transform K8s signals into LLM prompts and parse AI responses

**Key Components:**
- `IncidentAnalyzer` class
  - `_build_prompt()` - Construct structured prompt for Gemini
  - `analyze()` - Call Gemini API and parse response

**Dependencies:**
- google.genai: Gemini AI client library
- config: For API key, model settings

**Prompt Engineering:**
```
Role: "You are an expert SRE analyzing a Kubernetes incident"
Data: JSON-formatted signals (pod info, events, logs, conditions)
Task: Analyze signals and provide structured response
Format: JSON with root_cause, confidence, evidence, recommendations
```

**API Configuration:**
- Model: `gemini-2.0-flash-exp` (fast, cost-effective)
- Temperature: `0.1` (low for deterministic responses)
- Response Mode: JSON for structured parsing

#### 4. **incident_reporter.py** - Report Formatting (288 lines)
**Purpose:** Format analysis results for display and export

**Key Components:**
- `IncidentReporter` class
  - `generate_markdown_report()` - Create markdown string
  - `display_analysis()` - Show in terminal (markdown/JSON)
  - `_display_markdown()` - Rich formatted terminal output
  - `_display_json()` - JSON syntax highlighting
  - `save_report()` - Export to file

**Dependencies:**
- Rich: Console, Panel, Table, Syntax highlighting

**Output Formats:**
1. **Terminal Markdown:** Rich UI with colors, tables, panels
2. **JSON:** Structured data for automation
3. **Markdown File:** Shareable documentation

#### 5. **config.py** - Configuration Management (50 lines)
**Purpose:** Centralized configuration from environment variables

**Key Components:**
- `Config` class - Loads from .env file
- `get_config()` - Singleton accessor
- `validate_required()` - Check for required fields

**Settings:**
- Gemini API: `GEMINI_API_KEY`, `LLM_MODEL`, `LLM_TEMPERATURE`
- Kubernetes: `K8S_NAMESPACE`, `K8S_CONTEXT`, `K8S_CLUSTER_NAME`
- Application: `LOG_LEVEL`, `OUTPUT_FORMAT`, `LLM_MAX_LOG_LINES`

#### 6. **logger.py** - Logging Setup (30 lines)
**Purpose:** Configure logging for user feedback and debugging

**Key Components:**
- `setup_logging()` - Initialize loggers
- `get_logger()` - Get logger instance

**Logging Strategy:**
- Console: Simple format for user messages
- File: Timestamped logs in `logs/k8s_triage_YYYYMMDD_HHMMSS.log`
- Dual output: All levels to file, INFO+ to console

---

## Technical Implementation

### Technology Stack

**Core Technologies:**
- **Python 3.13** (compatible with 3.9+)
- **Kubernetes Python Client 28.0.0** - K8s API interaction
- **Google Gemini AI** (`google-genai 0.8.0`) - LLM analysis
- **Click 8.1.0** - CLI framework
- **Rich 13.0.0** - Terminal UI
- **python-dotenv 1.0.0** - Environment config

**Development Tools:**
- **venv** - Virtual environment
- **pip** - Package management
- **setuptools** - Packaging (console_scripts entry point)

### Code Organization

```
k8s-ai-troubleshooter/
├── k8s_ai_triage/              # Main package (1203 lines total)
│   ├── __init__.py             # Package metadata (10 lines)
│   ├── cli.py                  # CLI entry point (246 lines)
│   ├── config.py               # Environment settings (50 lines)
│   ├── logger.py               # Logging setup (30 lines)
│   ├── kubernetes_collector.py # Kubernetes data collection (379 lines)
│   ├── incident_analyzer.py    # AI analysis (194 lines)
│   └── incident_reporter.py    # Report formatting (288 lines)
├── logs/                       # Application logs (gitignored)
├── .env                        # Environment config (user-specific)
├── requirements.txt            # Python dependencies
├── setup.py                    # Package setup
└── README.md                   # User documentation
```

**Design Philosophy:**
- **Flat package structure** - A small CLI project is easier to review when the main modules live together
- **Single responsibility** - Each module has one clear purpose
- **Simple data structures** - Plain dicts, not complex objects
- **Minimal dependencies** - Only essential libraries
- **Production-ready** - Error handling, logging, cost controls

### Key Design Patterns

#### 1. **Pipeline Pattern** (CLI orchestration)
```python
# cli.py - pod() command
signals = collector.collect_all_signals(pod_name)  # Step 1
analysis = analyzer.analyze(signals)                # Step 2
reporter.display_analysis(report)                   # Step 3
```

#### 2. **Singleton Pattern** (Config)
```python
# config.py
_config = None

def get_config(**overrides):
    global _config
    if _config is None:
        _config = Config()
    return _config
```

#### 3. **Builder Pattern** (Prompt construction)
```python
# incident_analyzer.py
def _build_prompt(signals):
    signal_summary = {...}  # Structure data
    prompt = f"""...{json.dumps(signal_summary)}..."""
    return prompt
```

#### 4. **Strategy Pattern** (Output formatting)
```python
# incident_reporter.py
def display_analysis(report, output_format="markdown"):
    if output_format == "json":
        self._display_json(report)
    else:
        self._display_markdown(report)
```

### Data Models

#### Signal Structure
```python
signals = {
    "pod_status": {
        "name": "my-app-xyz",
        "namespace": "production",
        "phase": "Running",
        "ready": "1/1",
        "restarts": 0,
        "age": "2 days",
        "node": "node-123",
        "pod_ip": "10.244.1.5",
        "conditions": [
            {"type": "Ready", "status": "True", "reason": None, ...},
            {"type": "Initialized", "status": "True", ...}
        ],
        "container_statuses": [
            {
                "name": "app",
                "ready": True,
                "restart_count": 0,
                "state": {"running": {"started_at": "2026-05-30T10:00:00Z"}}
            }
        ]
    },
    "pod_events": {
        "events": [
            {
                "type": "Warning",
                "reason": "BackOff",
                "message": "Back-off restarting failed container",
                "count": 5,
                "first_timestamp": "2026-05-31T10:00:00Z",
                "last_timestamp": "2026-05-31T10:05:00Z"
            }
        ],
        "warning_count": 3,
        "error_count": 1,
        "latest_event_time": "2026-05-31T10:05:00Z"
    },
    "pod_logs": [
        {
            "container_name": "app",
            "logs": "2026-05-31T10:00:00Z INFO ...\n...",
            "line_count": 200,
            "truncated": True
        }
    ],
    "pod_describe": {
        "raw_output": "Name: my-app-xyz\nNamespace: ...",
        "events": ["Warning: BackOff - ..."],
        "conditions": ["Ready: True", ...]
    },
    "collected_at": "2026-05-31T23:00:00+00:00"
}
```

#### Analysis Structure
```python
analysis = {
    "root_cause": "Application experiencing OOMKilled due to memory limit exceeded",
    "confidence": "HIGH",
    "supporting_evidence": [
        "Pod restarted 5 times in last hour",
        "Last event: 'OOMKilled' - Container exceeded memory limit",
        "Logs show: 'java.lang.OutOfMemoryError: Java heap space'"
    ],
    "recommendations": [
        "Increase memory limits in deployment spec (current: 512Mi → suggested: 1Gi)",
        "Review application memory profiling to identify leaks",
        "Add memory usage alerts to monitoring dashboard"
    ],
    "additional_context": "Pattern suggests memory leak in request handling code",
    "raw_response": "{...full LLM response...}"
}
```

### API Integration

#### Kubernetes API
```python
# Load kubeconfig
from kubernetes import client, config

config.load_kube_config()  # or config.load_kube_config(context="prod")
v1 = client.CoreV1Api()

# Fetch pod
pod = v1.read_namespaced_pod(name="my-app-xyz", namespace="default")

# Fetch events
events = v1.list_namespaced_event(
    namespace="default",
    field_selector=f"involvedObject.name={pod_name}"
)

# Fetch logs
logs = v1.read_namespaced_pod_log(
    name="my-app-xyz",
    namespace="default",
    container="app",
    tail_lines=200,
    timestamps=True
)
```

#### Gemini API
```python
from google import genai

client = genai.Client(api_key="...")

response = client.models.generate_content(
    model="gemini-2.0-flash-exp",
    contents=prompt,
    config={
        "temperature": 0.1,
        "response_mime_type": "application/json"
    }
)

analysis_data = json.loads(response.text)
```

---
