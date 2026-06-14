"""
Incident Report Generation and Display Module

This module handles the presentation layer of the k8s-triage tool. It takes raw analysis
data and formats it into beautiful, readable reports for both terminal display and file
export.

Supported Output Formats:
1. Markdown (terminal): Rich terminal UI with colors, tables, and panels
2. JSON: Machine-readable structured output for automation
3. Markdown (file): Standard markdown for documentation/sharing

Rich Terminal Features:
- Color-coded status indicators (green=Running, red=Failed, yellow=Pending)
- Tables for structured data (service info, signal summary, events)
- Panels with borders for visual separation
- Confidence level highlighting (green=HIGH, yellow=MEDIUM, red=LOW)
- Progress indicators during analysis
- Emoji and Unicode symbols for visual appeal

Report Sections:
1. Header: Service name, namespace, timestamp
2. Service Information: Pod status, readiness, restarts, age, node
3. Root Cause Analysis: Confidence level + probable root cause
4. Supporting Evidence: Numbered list of specific signals
5. Remediation Recommendations: Actionable next steps
6. Additional Context: Extra insights from AI
7. Signal Summary: Event counts, container counts
8. Recent Events: Last 5 events with type, reason, message

Display Logic:
- Terminal output: Uses Rich library for interactive, colored display
- File output: Plain text (markdown) or JSON based on extension
- JSON includes full nested structure for programmatic access

Usage:
    reporter = IncidentReporter()
    
    # Display in terminal
    reporter.display_analysis(report_dict, output_format="markdown")
    
    # Save to file
    reporter.save_report(report_dict, "incident-report.md")
    reporter.save_report(report_dict, "incident-report.json")

Color Coding:
- Running/Succeeded: Green
- Failed/Unknown: Red  
- Pending: Yellow
- Confidence HIGH: Green
- Confidence MEDIUM: Yellow
- Confidence LOW: Red

The module is designed to be:
- User-friendly: Clear, scannable output
- Information-dense: All relevant data visible
- Export-friendly: Shareable markdown reports
- Automation-friendly: JSON output for CI/CD integration
"""
import json
import logging
from typing import Literal, Dict, Any
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax

logger = logging.getLogger("k8s_ai_triage")


class IncidentReporter:
    """Generates formatted incident reports."""
    
    def __init__(self):
        """Initialize the reporter."""
        self.console = Console()
    
    def generate_markdown_report(self, report: Dict[str, Any]) -> str:
        """
        Generate a markdown report.
        
        Args:
            report: Complete incident report
            
        Returns:
            Markdown formatted string
        """
        md_lines = []
        
        # Header
        md_lines.append(f"# Kubernetes Incident Triage Report")
        md_lines.append(f"**Generated:** {report["generated_at"].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        md_lines.append("")
        
        # Service Info
        md_lines.append(f"## Service Information")
        md_lines.append(f"- **Pod:** `{report["service_name"]}`")
        md_lines.append(f"- **Namespace:** `{report["namespace"]}`")
        md_lines.append(f"- **Status:** {report["signals"]["pod_status"]["phase"]}")
        md_lines.append(f"- **Ready:** {report["signals"]["pod_status"]["ready"]}")
        md_lines.append(f"- **Restarts:** {report["signals"]["pod_status"]["restarts"]}")
        md_lines.append(f"- **Age:** {report["signals"]["pod_status"]["age"]}")
        md_lines.append(f"- **Node:** {report["signals"]["pod_status"]["node"]}")
        md_lines.append("")
        
        # Analysis
        md_lines.append(f"## Root Cause Analysis")
        md_lines.append(f"**Confidence:** {report["analysis"]["confidence"]}")
        md_lines.append("")
        md_lines.append(f"### Probable Root Cause")
        md_lines.append(report["analysis"]["root_cause"])
        md_lines.append("")
        
        # Supporting Evidence
        md_lines.append(f"### Supporting Evidence")
        for i, evidence in enumerate(report["analysis"]["supporting_evidence"], 1):
            md_lines.append(f"{i}. {evidence}")
        md_lines.append("")
        
        # Recommendations
        md_lines.append(f"### Remediation Recommendations")
        for i, rec in enumerate(report["analysis"]["recommendations"], 1):
            md_lines.append(f"{i}. {rec}")
        md_lines.append("")
        
        # Additional Context
        if report["analysis"]["additional_context"]:
            md_lines.append(f"### Additional Context")
            md_lines.append(report["analysis"]["additional_context"])
            md_lines.append("")
        
        # Signal Summary
        md_lines.append(f"## Signal Summary")
        md_lines.append(f"- **Events:** {len(report["signals"]["pod_events"]["events"])} total, "
                       f"{report["signals"]["pod_events"]["warning_count"]} warnings, "
                       f"{report["signals"]["pod_events"]["error_count"]} errors")
        md_lines.append(f"- **Containers:** {len(report["signals"]["pod_logs"])}")
        md_lines.append("")
        
        # Recent Events
        if report["signals"]["pod_events"]["events"]:
            md_lines.append(f"### Recent Events")
            for event in report["signals"]["pod_events"]["events"][:5]:
                md_lines.append(
                    f"- **{event['type']}:** {event['reason']} - {event['message']} "
                    f"(count: {event['count']})"
                )
            md_lines.append("")
        
        return "\n".join(md_lines)
    
    def display_analysis(
        self,
        report: Dict[str, Any],
        output_format: Literal["markdown", "json"] = "markdown"
    ) -> None:
        """
        Display incident analysis in the terminal.
        
        Args:
            report: Complete incident report
            output_format: Output format (markdown or json)
        """
        if output_format == "json":
            self._display_json(report)
        else:
            self._display_markdown(report)
    
    def _display_json(self, report: Dict[str, Any]) -> None:
        """Display report as JSON."""
        report_dict = {
            "service_name": report["service_name"],
            "namespace": report["namespace"],
            "generated_at": report["generated_at"].isoformat(),
            "pod_status": {
                "phase": report["signals"]["pod_status"]["phase"],
                "ready": report["signals"]["pod_status"]["ready"],
                "restarts": report["signals"]["pod_status"]["restarts"],
                "age": report["signals"]["pod_status"]["age"],
                "node": report["signals"]["pod_status"]["node"]
            },
            "analysis": {
                "root_cause": report["analysis"]["root_cause"],
                "confidence": report["analysis"]["confidence"],
                "supporting_evidence": report["analysis"]["supporting_evidence"],
                "recommendations": report["analysis"]["recommendations"],
                "additional_context": report["analysis"]["additional_context"]
            },
            "events_summary": {
                "total": len(report["signals"]["pod_events"]["events"]),
                "warnings": report["signals"]["pod_events"]["warning_count"],
                "errors": report["signals"]["pod_events"]["error_count"]
            }
        }
        
        json_output = json.dumps(report_dict, indent=2)
        syntax = Syntax(json_output, "json", theme="monokai", line_numbers=False)
        self.console.print(syntax)
    
    def _display_markdown(self, report: Dict[str, Any]) -> None:
        """Display report as formatted markdown."""
        self.console.print()
        
        # Title
        self.console.print(
            Panel.fit(
                f"[bold cyan]Kubernetes Incident Triage Report[/bold cyan]\n"
                f"[dim]{report["generated_at"].strftime('%Y-%m-%d %H:%M:%S UTC')}[/dim]",
                border_style="cyan"
            )
        )
        self.console.print()
        
        # Service Info Table
        service_table = Table(title="Service Information", show_header=False, box=None)
        service_table.add_column("Field", style="bold")
        service_table.add_column("Value")
        
        service_table.add_row("Pod", f"[cyan]{report["service_name"]}[/cyan]")
        service_table.add_row("Namespace", f"[cyan]{report["namespace"]}[/cyan]")
        service_table.add_row("Status", self._colorize_status(report["signals"]["pod_status"]["phase"]))
        service_table.add_row("Ready", report["signals"]["pod_status"]["ready"])
        service_table.add_row("Restarts", str(report["signals"]["pod_status"]["restarts"]))
        service_table.add_row("Age", report["signals"]["pod_status"]["age"])
        service_table.add_row("Node", report["signals"]["pod_status"]["node"] or "N/A")
        
        self.console.print(service_table)
        self.console.print()
        
        # Root Cause Analysis
        confidence_color = {
            "HIGH": "green",
            "MEDIUM": "yellow",
            "LOW": "red"
        }.get(report["analysis"]["confidence"], "white")
        
        self.console.print(
            Panel(
                f"[bold]Confidence:[/bold] [{confidence_color}]{report["analysis"]["confidence"]}[/{confidence_color}]\n\n"
                f"[bold]Root Cause:[/bold]\n{report["analysis"]["root_cause"]}",
                title="[bold yellow]Root Cause Analysis[/bold yellow]",
                border_style="yellow"
            )
        )
        self.console.print()
        
        # Supporting Evidence
        self.console.print("[bold green]Supporting Evidence:[/bold green]")
        for i, evidence in enumerate(report["analysis"]["supporting_evidence"], 1):
            self.console.print(f"  {i}. {evidence}")
        self.console.print()
        
        # Recommendations
        self.console.print("[bold blue]Remediation Recommendations:[/bold blue]")
        for i, rec in enumerate(report["analysis"]["recommendations"], 1):
            self.console.print(f"  {i}. {rec}")
        self.console.print()
        
        # Additional Context
        if report["analysis"]["additional_context"]:
            self.console.print(
                Panel(
                    report["analysis"]["additional_context"],
                    title="[bold]Additional Context[/bold]",
                    border_style="dim"
                )
            )
            self.console.print()
        
        # Signal Summary
        signals_table = Table(title="Signal Summary", show_header=True)
        signals_table.add_column("Metric", style="bold")
        signals_table.add_column("Value", justify="right")
        
        signals_table.add_row("Total Events", str(len(report["signals"]["pod_events"]["events"])))
        signals_table.add_row("Warning Events", f"[yellow]{report["signals"]["pod_events"]["warning_count"]}[/yellow]")
        signals_table.add_row("Error Events", f"[red]{report["signals"]["pod_events"]["error_count"]}[/red]")
        signals_table.add_row("Containers", str(len(report["signals"]["pod_logs"])))
        
        self.console.print(signals_table)
        self.console.print()
        
        # Recent Events
        if report["signals"]["pod_events"]["events"]:
            events_table = Table(title="Recent Events (Last 5)", show_header=True)
            events_table.add_column("Type", style="bold")
            events_table.add_column("Reason")
            events_table.add_column("Message", max_width=60)
            events_table.add_column("Count", justify="right")
            
            for event in report["signals"]["pod_events"]["events"][:5]:
                event_type = event['type']
                type_color = "yellow" if event_type == "Warning" else "white"
                events_table.add_row(
                    f"[{type_color}]{event_type}[/{type_color}]",
                    event['reason'],
                    event['message'][:60],
                    str(event['count'])
                )
            
            self.console.print(events_table)
            self.console.print()
    
    def _colorize_status(self, phase: str) -> str:
        """Colorize pod phase for display."""
        colors = {
            "Running": "green",
            "Succeeded": "green",
            "Pending": "yellow",
            "Failed": "red",
            "Unknown": "red"
        }
        color = colors.get(phase, "white")
        return f"[{color}]{phase}[/{color}]"
    
    def save_report(self, report: Dict[str, Any], file_path: str) -> None:
        """
        Save report to a file.
        
        Args:
            report: Complete incident report
            file_path: Path to save the report
        """
        logger.info(f"Saving report to: {file_path}")
        
        if file_path.endswith('.json'):
            # Save as JSON
            report_dict = report(mode='json')
            with open(file_path, 'w') as f:
                json.dump(report_dict, f, indent=2, default=str)
        else:
            # Save as Markdown
            markdown = self.generate_markdown_report(report)
            with open(file_path, 'w') as f:
                f.write(markdown)
        
        logger.info(f"Report saved successfully to: {file_path}")
