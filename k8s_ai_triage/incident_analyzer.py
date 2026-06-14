"""
AI-Powered Incident Analysis Module

This module integrates with Google Gemini AI to perform intelligent root cause analysis
of Kubernetes incidents. It transforms raw Kubernetes signals into structured prompts
and parses AI responses into actionable insights.

Core Functionality:
1. Prompt Engineering: Converts K8s signals into structured prompts for LLM
2. LLM Integration: Calls Gemini API with optimized settings
3. Response Parsing: Extracts root cause, confidence, evidence, and recommendations
4. Error Handling: Gracefully handles API failures and malformed responses

Prompt Design:
The prompt follows a structured format:
- Context: "You are an expert SRE analyzing a Kubernetes incident"
- Data: JSON-formatted pod info, events, logs, conditions
- Instructions: Specific analysis requirements (root cause, evidence, remediation)
- Format: JSON response schema for structured output

This design ensures:
- Consistent, parseable responses
- Evidence-based analysis (references specific log lines, events)
- Actionable recommendations (not generic advice)

Gemini API Configuration:
- Model: gemini-2.0-flash-exp (fast, cost-effective) or gemini-1.5-flash
- Temperature: 0.1 (low for deterministic, focused responses)
- Response Format: JSON mode for structured output
- Token Limits: Controlled via log truncation in collector

Analysis Output Structure:
{
    "root_cause": "Brief description of the issue",
    "confidence": "HIGH/MEDIUM/LOW",
    "supporting_evidence": [
        "Specific log line showing error",
        "Event message indicating problem",
        "Container restart count of 5"
    ],
    "recommendations": [
        "Increase memory limit to 1Gi",
        "Check application logs for NPE",
        "Review recent deployments"
    ],
    "additional_context": "Extra insights or patterns noticed",
    "raw_response": "Full LLM response for debugging"
}

Error Handling:
- API failures: Wrapped in RuntimeError with helpful message
- JSON parse errors: Returns fallback response with raw LLM output
- Missing fields: Defaults to "Unknown" or empty lists

Cost Optimization:
- Log truncation before sending (configured in collector)
- Efficient JSON prompts (no unnecessary verbosity)
- Low temperature (fewer tokens in response)
- Focus on recent events (last 10, not all)

Usage:
    analyzer = IncidentAnalyzer()
    analysis = analyzer.analyze(signals_dict)
    print(analysis["root_cause"])
    print(analysis["confidence"])
"""
import json
import logging
from typing import Dict, Any

from google import genai

from k8s_ai_triage.config import get_config

logger = logging.getLogger("k8s_ai_triage")


class IncidentAnalyzer:
    """Analyzes Kubernetes incidents using Gemini AI."""
    
    def __init__(self):
        """Initialize the incident analyzer."""
        self.config = get_config()
        
        # Initialize Gemini client
        try:
            self.client = genai.Client(api_key=self.config.gemini_api_key)
            logger.info(f"Initialized Gemini client with model: {self.config.llm_model}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise RuntimeError(f"Cannot initialize Gemini client. Check your API key. Error: {e}")
    
    def _build_prompt(self, signals: Dict[str, Any]) -> str:
        """
        Build the analysis prompt from collected signals.
        
        Args:
            signals: Collected Kubernetes signals
            
        Returns:
            Formatted prompt string for LLM
        """
        # Build structured signal summary
        signal_summary = {
            "pod_info": {
                "name": signals["pod_status"]["name"],
                "namespace": signals["pod_status"]["namespace"],
                "phase": signals["pod_status"]["phase"],
                "ready": signals["pod_status"]["ready"],
                "restarts": signals["pod_status"]["restarts"],
                "age": signals["pod_status"]["age"],
                "node": signals["pod_status"]["node"]
            },
            "conditions": [
                {
                    "type": c["type"],
                    "status": c["status"],
                    "reason": c.get("reason"),
                    "message": c.get("message")
                }
                for c in signals["pod_status"]["conditions"]
            ],
            "container_statuses": signals["pod_status"]["container_statuses"],
            "events_summary": {
                "total_events": len(signals["pod_events"]["events"]),
                "warning_count": signals["pod_events"]["warning_count"],
                "error_count": signals["pod_events"]["error_count"],
                "recent_events": signals["pod_events"]["events"][:5]  # Last 5 events
            },
            "logs_summary": {
                "containers": [
                    {
                        "name": log["container_name"],
                        "line_count": log["line_count"],
                        "truncated": log["truncated"],
                        "has_error": log.get("error") is not None,
                        "recent_logs": log["logs"].split('\n')[-50:] if log["logs"] else []  # Last 50 lines
                    }
                    for log in signals["pod_logs"]
                ]
            }
        }
        
        prompt = f"""You are an expert Site Reliability Engineer analyzing a Kubernetes incident.

**Task:** Analyze the following Kubernetes signals and provide a structured incident triage report.

**Pod Information:**
{json.dumps(signal_summary, indent=2)}

**Recent Events:**
{json.dumps(signals["pod_events"]["events"][:10], indent=2)}

**Pod Describe Output:**
{signals["pod_describe"]["raw_output"]}

**Instructions:**
1. Analyze all the signals above (pod status, events, logs, conditions)
2. Identify the most probable root cause of any issues
3. Assess your confidence level (HIGH/MEDIUM/LOW) based on evidence strength
4. List specific supporting evidence from the signals
5. Provide actionable remediation recommendations

**Response Format (JSON):**
{{
  "root_cause": "Brief description of the probable root cause",
  "confidence": "HIGH/MEDIUM/LOW",
  "supporting_evidence": [
    "Evidence point 1 from the signals",
    "Evidence point 2 from the signals",
    "Evidence point 3 from the signals"
  ],
  "recommendations": [
    "Specific action 1 to resolve the issue",
    "Specific action 2 to prevent recurrence",
    "Specific action 3 for monitoring"
  ],
  "additional_context": "Any additional relevant information or patterns noticed"
}}

**Important:**
- Base your analysis ONLY on the provided signals
- Be specific in your evidence (reference actual log lines, event messages, etc.)
- Provide actionable recommendations, not generic advice
- If the pod appears healthy, say so clearly
- Consider restart counts, event patterns, and state transitions

Respond ONLY with valid JSON matching the format above.
"""
        
        return prompt
    
    def analyze(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze Kubernetes signals using Gemini.
        
        Args:
            signals: Collected Kubernetes signals
            
        Returns:
            AnalysisResult with root cause and recommendations
        """
        logger.info("Analyzing signals with Gemini AI")
        
        # Build prompt
        prompt = self._build_prompt(signals)
        logger.debug(f"Prompt length: {len(prompt)} characters")
        
        try:
            # Call Gemini API
            response = self.client.models.generate_content(
                model=self.config.llm_model,
                contents=prompt,
                config={
                    "temperature": self.config.llm_temperature,
                    "response_mime_type": "application/json"
                }
            )
            
            raw_response = response.text
            logger.debug(f"Gemini response received ({len(raw_response)} chars)")
            
            # Parse JSON response
            try:
                analysis_data = json.loads(raw_response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini response as JSON: {e}")
                logger.debug(f"Raw response: {raw_response}")
                
                # Fallback: create structured response from raw text
                analysis_data = {
                    "root_cause": "Analysis completed but response format was unexpected",
                    "confidence": "LOW",
                    "supporting_evidence": ["Raw LLM response available in report"],
                    "recommendations": ["Review raw analysis output"],
                    "additional_context": raw_response[:500]
                }
            
            # Create analysis result dict
            result = {
                "root_cause": analysis_data.get("root_cause", "Unknown"),
                "confidence": analysis_data.get("confidence", "LOW"),
                "supporting_evidence": analysis_data.get("supporting_evidence", []),
                "recommendations": analysis_data.get("recommendations", []),
                "additional_context": analysis_data.get("additional_context"),
                "raw_response": raw_response
            }
            
            logger.info(f"Analysis complete. Root cause: {result['root_cause']}")
            return result
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise RuntimeError(f"Failed to analyze with Gemini: {e}")
