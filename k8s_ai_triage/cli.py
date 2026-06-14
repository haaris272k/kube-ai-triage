"""
Command-Line Interface (CLI) Module

This is the main entry point for the k8s-triage command-line tool. It uses the Click
framework to provide a user-friendly CLI with multiple commands and options.

Architecture:
- Click framework for argument parsing and command routing
- Rich library for beautiful terminal output (colors, tables, progress indicators)
- Orchestrates the entire analysis pipeline: collect → analyze → report

Commands:
1. pod <pod-name>: Analyze a specific pod for issues
   - Collects Kubernetes signals (status, logs, events)
   - Sends to Gemini AI for root cause analysis
   - Displays formatted report in terminal
   - Optionally saves to file (--save flag)

2. deployment <name>: (Future) Analyze all pods in a deployment

3. version: Display version and tool information

Global Options:
- --namespace, -n: Override default Kubernetes namespace
- --context: Use specific kubectl context
- --output, -o: Choose output format (markdown/json)
- --debug: Enable verbose debug logging
- --interactive, -i: (Future) Interactive pod selection mode

Execution Flow:
1. Parse CLI arguments and setup logging
2. Validate configuration (check for API key)
3. Initialize collector, analyzer, and reporter
4. Execute the analysis pipeline:
   a. Collect K8s signals (pod status, events, logs)
   b. Analyze with Gemini AI (root cause + recommendations)
   c. Generate and display formatted report
5. Optionally save report to file
6. Handle errors gracefully with user-friendly messages

Error Handling:
- ValueError: Pod not found or invalid input → Exit code 1
- RuntimeError: K8s connection or LLM API errors → Exit code 1
- KeyboardInterrupt: User cancellation → Exit code 130
- Unexpected errors: Log traceback and exit code 1

Usage Examples:
    k8s-triage pod my-app-xyz
    k8s-triage pod my-app-xyz -n production --save report.md
    k8s-triage pod my-app-xyz --debug -o json
"""
import sys
from typing import Optional
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from k8s_ai_triage.config import get_config
from k8s_ai_triage.logger import setup_logging, get_logger
from k8s_ai_triage.kubernetes_collector import KubernetesCollector
from k8s_ai_triage.incident_analyzer import IncidentAnalyzer
from k8s_ai_triage.incident_reporter import IncidentReporter


console = Console()


@click.group(invoke_without_command=True)
@click.option(
    "--namespace", "-n",
    default=None,
    help="Kubernetes namespace (defaults to config)"
)
@click.option(
    "--context",
    default=None,
    help="Kubernetes context to use"
)
@click.option(
    "--output", "-o",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    default=None,
    help="Output format"
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging"
)
@click.option(
    "--interactive", "-i",
    is_flag=True,
    help="Interactive mode for pod selection"
)
@click.pass_context
def cli(
    ctx: click.Context,
    namespace: Optional[str],
    context: Optional[str],
    output: Optional[str],
    debug: bool,
    interactive: bool
):
    """
    🔍 K8s AI Triage - Intelligent Kubernetes Incident Analysis
    
    Automatically collects Kubernetes signals and generates AI-powered
    root cause analysis with remediation recommendations.
    
    Examples:
    
        # Analyze a specific pod
        k8s-triage pod my-app-7d9f8b-xyz
        
        # Analyze a deployment (auto-discovers pods)
        k8s-triage deployment my-app
        
        # Interactive mode
        k8s-triage --interactive
        
        # Specify namespace
        k8s-triage pod my-app-xyz -n production
    """
    # Initialize config
    config_overrides = {}
    if namespace:
        config_overrides["k8s_namespace"] = namespace
    if context:
        config_overrides["k8s_context"] = context
    if output:
        config_overrides["output_format"] = output
    if debug:
        config_overrides["log_level"] = "DEBUG"
    
    config = get_config(**config_overrides)
    
    # Validate required config
    try:
        config.validate_required()
    except ValueError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        console.print("\n[yellow]Tip:[/yellow] Copy .env.example to .env and add your GEMINI_API_KEY")
        sys.exit(1)
    
    # Setup logging
    logger = setup_logging(log_level=config.log_level)
    logger.debug(f"Config: namespace={config.k8s_namespace}, model={config.llm_model}")
    
    # Store config in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["logger"] = logger
    
    # If no subcommand and not interactive, show help
    if ctx.invoked_subcommand is None and not interactive:
        console.print(Panel.fit(
            "[bold cyan]K8s AI Triage[/bold cyan]\n\n"
            "Use --help to see available commands",
            border_style="cyan"
        ))
        click.echo(ctx.get_help())
        sys.exit(0)
    
    # Interactive mode (to be implemented in Phase 2)
    if interactive and ctx.invoked_subcommand is None:
        console.print("[yellow]Interactive mode will be available in Phase 2[/yellow]")
        sys.exit(0)


@cli.command()
@click.argument("pod_name")
@click.option('--save', '-s', help='Save report to file')
@click.pass_context
def pod(ctx: click.Context, pod_name: str, save: Optional[str]):
    """
    Analyze a specific pod.
    
    Example: k8s-triage pod my-app-7d9f8b-xyz
    """
    config = ctx.obj["config"]
    logger = ctx.obj["logger"]
    
    logger.info(f"Starting pod analysis: {pod_name}")
    logger.info(f"Namespace: {config.k8s_namespace}")
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            # Step 1: Collect Kubernetes signals
            task = progress.add_task("[cyan]Collecting Kubernetes signals...", total=None)
            collector = KubernetesCollector(namespace=config.k8s_namespace, context=config.k8s_context)
            signals = collector.collect_all_signals(pod_name)
            progress.update(task, description="[green]✓ Signals collected")
            progress.stop_task(task)
            
            # Step 2: Analyze with AI
            task = progress.add_task("[cyan]Analyzing with Gemini AI...", total=None)
            analyzer = IncidentAnalyzer()
            analysis = analyzer.analyze(signals)
            progress.update(task, description="[green]✓ Analysis complete")
            progress.stop_task(task)
            
            # Step 3: Generate report
            task = progress.add_task("[cyan]Generating report...", total=None)
            report = {
                "service_name": pod_name,
                "namespace": signals["pod_status"]["namespace"],
                "signals": signals,
                "analysis": analysis,
                "generated_at": datetime.utcnow()
            }
            progress.update(task, description="[green]✓ Report generated")
            progress.stop_task(task)
        
        console.print()
        
        # Display the report
        reporter = IncidentReporter()
        output_format = config.output_format if hasattr(config, 'output_format') else 'markdown'
        reporter.display_analysis(report, output_format=output_format)
        
        # Save if requested
        if save:
            reporter.save_report(report, save)
            console.print(f"\n[green]✓ Report saved to: {save}[/green]\n")
        
        logger.info("Pod analysis completed successfully")
        
    except ValueError as e:
        console.print(f"\n[red]Error:[/red] {str(e)}\n")
        logger.error(f"Validation error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"\n[red]Error:[/red] {str(e)}\n")
        logger.error(f"Runtime error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis interrupted by user[/yellow]\n")
        logger.warning("Analysis interrupted by user")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Unexpected error:[/red] {str(e)}\n")
        logger.exception("Unexpected error during pod analysis")
        sys.exit(1)


@cli.command()
@click.argument("deployment_name")
@click.pass_context
def deployment(ctx: click.Context, deployment_name: str):
    """
    Analyze a deployment (auto-discovers pods).
    
    Example: k8s-triage deployment my-app
    """
    config = ctx.obj["config"]
    logger = ctx.obj["logger"]
    
    console.print(f"\n[cyan]Analyzing deployment:[/cyan] {deployment_name}")
    console.print(f"[cyan]Namespace:[/cyan] {config.k8s_namespace}")
    
    # TODO: Implement in Phase 2
    console.print("\n[yellow]Deployment analysis will be implemented in Phase 2[/yellow]")
    logger.info(f"Deployment analysis requested: {deployment_name}")


@cli.command()
@click.pass_context
def version(ctx: click.Context):
    """Show version information."""
    console.print(Panel.fit(
        "[bold cyan]K8s AI Triage[/bold cyan]\n"
        "Version: 0.1.0 (MVP)\n"
        "Author: Haaris\n"
        "Purpose: AI-powered Kubernetes incident triage",
        border_style="cyan"
    ))


def main():
    """Main entrypoint."""
    try:
        cli(obj={})
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
