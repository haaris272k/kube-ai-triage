"""
Kubernetes Signal Collection Module

This module is responsible for collecting comprehensive troubleshooting data from a
Kubernetes cluster using the official Kubernetes Python client library. It gathers
all relevant signals needed for AI-powered incident analysis.

What It Collects:
1. Pod Status: Phase, readiness, restart count, age, node assignment, IP address
2. Pod Conditions: Ready, Initialized, PodScheduled conditions with reasons
3. Container Statuses: Running/Waiting/Terminated states, restart counts, exit codes
4. Pod Events: Recent events (Normal/Warning), with timestamps and counts
5. Pod Logs: Last N lines from each container (configurable for cost control)
6. Pod Describe: Human-readable summary similar to 'kubectl describe pod'

Design Decisions:
- Uses Kubernetes Python client (not kubectl subprocess) for reliability
- Returns plain Python dicts instead of complex objects for simplicity
- Implements cost controls (max log lines) to limit LLM token usage
- Graceful error handling: missing logs return empty instead of crashing
- Timestamps all data collection for audit trails

Kubernetes API Integration:
- Loads kubeconfig from default location (~/.kube/config)
- Supports custom context selection
- Uses CoreV1Api for pod-related operations
- Handles ApiException for 404 (pod not found) and other errors

Data Structure:
Returns nested dicts with the following structure:
{
    "pod_status": {"name", "namespace", "phase", "ready", "restarts", ...},
    "pod_events": {"events": [...], "warning_count", "error_count", ...},
    "pod_logs": [{"container_name", "logs", "line_count", "truncated"}, ...],
    "pod_describe": {"raw_output", "events", "conditions"},
    "collected_at": <timestamp>
}

Cost Optimization:
- Log truncation: Only last N lines (default: 200) sent to LLM
- Event filtering: Focus on recent and relevant events
- No metrics collection (future enhancement)

Usage:
    collector = KubernetesCollector(namespace="production")
    signals = collector.collect_all_signals("my-pod-xyz")
    print(signals["pod_status"]["phase"])  # Access collected data
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from k8s_ai_triage.config import get_config

logger = logging.getLogger("k8s_ai_triage")


class KubernetesCollector:
    """Collects Kubernetes signals for incident analysis."""
    
    def __init__(self, namespace: Optional[str] = None, context: Optional[str] = None):
        """
        Initialize Kubernetes collector.
        
        Args:
            namespace: Kubernetes namespace (defaults to config)
            context: Kubernetes context to use (optional)
        """
        self.config = get_config()
        self.namespace = namespace or self.config.k8s_namespace
        self.context = context or self.config.k8s_context
        
        # Initialize Kubernetes client
        self._init_k8s_client()
        
        logger.info(f"Initialized K8s collector for namespace: {self.namespace}")
    
    def _init_k8s_client(self) -> None:
        """Initialize Kubernetes client configuration."""
        try:
            # Try to load from default kubeconfig
            if self.context:
                config.load_kube_config(context=self.context)
                logger.debug(f"Loaded kubeconfig with context: {self.context}")
            else:
                config.load_kube_config()
                logger.debug("Loaded kubeconfig from default location")
            
            self.v1 = client.CoreV1Api()
            
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")
            raise RuntimeError(
                f"Cannot connect to Kubernetes cluster. "
                f"Ensure kubectl is configured and you have access. Error: {e}"
            )
    
    def collect_pod_status(self, pod_name: str) -> Dict[str, Any]:
        """
        Collect pod status information.
        
        Args:
            pod_name: Name of the pod
            
        Returns:
            PodStatus model with pod information
        """
        logger.info(f"Collecting pod status for: {pod_name}")
        
        try:
            pod = self.v1.read_namespaced_pod(name=pod_name, namespace=self.namespace)
            
            # Calculate ready status
            ready_containers = sum(
                1 for cs in pod.status.container_statuses or []
                if cs.ready
            )
            total_containers = len(pod.status.container_statuses or [])
            ready_str = f"{ready_containers}/{total_containers}"
            
            # Calculate total restarts
            total_restarts = sum(
                cs.restart_count for cs in pod.status.container_statuses or []
            )
            
            # Calculate age
            created = pod.metadata.creation_timestamp
            age = str(datetime.now(timezone.utc) - created).split('.')[0]
            
            # Extract conditions
            conditions = [
                {
                    "type": c.type,
                    "status": c.status,
                    "reason": c.reason,
                    "message": c.message,
                    "last_transition_time": str(c.last_transition_time)
                }
                for c in (pod.status.conditions or [])
            ]
            
            # Extract container statuses
            container_statuses = []
            for cs in (pod.status.container_statuses or []):
                status_info = {
                    "name": cs.name,
                    "ready": cs.ready,
                    "restart_count": cs.restart_count,
                    "state": {}
                }
                
                # Get current state
                if cs.state.running:
                    status_info["state"]["running"] = {
                        "started_at": str(cs.state.running.started_at)
                    }
                elif cs.state.waiting:
                    status_info["state"]["waiting"] = {
                        "reason": cs.state.waiting.reason,
                        "message": cs.state.waiting.message
                    }
                elif cs.state.terminated:
                    status_info["state"]["terminated"] = {
                        "reason": cs.state.terminated.reason,
                        "exit_code": cs.state.terminated.exit_code,
                        "message": cs.state.terminated.message
                    }
                
                container_statuses.append(status_info)
            
            return {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "phase": pod.status.phase,
                "ready": ready_str,
                "restarts": total_restarts,
                "age": age,
                "node": pod.spec.node_name,
                "pod_ip": pod.status.pod_ip,
                "conditions": conditions,
                "container_statuses": container_statuses
            }
            
        except ApiException as e:
            if e.status == 404:
                logger.error(f"Pod not found: {pod_name}")
                raise ValueError(f"Pod '{pod_name}' not found in namespace '{self.namespace}'")
            else:
                logger.error(f"Kubernetes API error: {e}")
                raise RuntimeError(f"Failed to get pod status: {e}")
    
    def collect_pod_events(self, pod_name: str) -> Dict[str, Any]:
        """
        Collect pod events.
        
        Args:
            pod_name: Name of the pod
            
        Returns:
            PodEvents model with event information
        """
        logger.info(f"Collecting events for pod: {pod_name}")
        
        try:
            # Get events related to this pod
            field_selector = f"involvedObject.name={pod_name}"
            events_list = self.v1.list_namespaced_event(
                namespace=self.namespace,
                field_selector=field_selector
            )
            
            events = []
            warning_count = 0
            error_count = 0
            latest_time = None
            
            for event in events_list.items:
                event_data = {
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "count": event.count,
                    "first_timestamp": str(event.first_timestamp),
                    "last_timestamp": str(event.last_timestamp)
                }
                events.append(event_data)
                
                # Count warnings and errors
                if event.type == "Warning":
                    warning_count += 1
                if "Error" in event.reason or "Failed" in event.reason:
                    error_count += 1
                
                # Track latest event
                if event.last_timestamp:
                    if latest_time is None or event.last_timestamp > latest_time:
                        latest_time = event.last_timestamp
            
            # Sort events by last timestamp (most recent first)
            events.sort(key=lambda x: x["last_timestamp"], reverse=True)
            
            return {
                "events": events,
                "warning_count": warning_count,
                "error_count": error_count,
                "latest_event_time": latest_time
            }
            
        except ApiException as e:
            logger.error(f"Failed to get pod events: {e}")
            return {"events": [], "warning_count": 0, "error_count": 0}
    
    def collect_pod_logs(self, pod_name: str, max_lines: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Collect pod logs.
        
        Args:
            pod_name: Name of the pod
            max_lines: Maximum number of log lines to collect (defaults to config)
            
        Returns:
            List of PodLogs (one per container)
        """
        max_lines = max_lines or self.config.llm_max_log_lines
        logger.info(f"Collecting logs for pod: {pod_name} (max {max_lines} lines)")
        
        pod_logs = []
        
        try:
            # Get pod to find container names
            pod = self.v1.read_namespaced_pod(name=pod_name, namespace=self.namespace)
            
            # Collect logs for each container
            for container in pod.spec.containers:
                container_name = container.name
                
                try:
                    # Get logs with tail to limit size
                    logs = self.v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=self.namespace,
                        container=container_name,
                        tail_lines=max_lines,
                        timestamps=True
                    )
                    
                    lines = logs.split('\n') if logs else []
                    line_count = len(lines)
                    truncated = line_count >= max_lines
                    
                    pod_logs.append({
                        "container_name": container_name,
                        "logs": logs,
                        "line_count": line_count,
                        "truncated": truncated
                    })
                    
                    logger.debug(f"Collected {line_count} log lines from container: {container_name}")
                    
                except ApiException as e:
                    logger.warning(f"Failed to get logs for container {container_name}: {e}")
                    pod_logs.append({
                        "container_name": container_name,
                        "logs": "",
                        "line_count": 0,
                        "error": str(e)
                    })
            
            return pod_logs
            
        except ApiException as e:
            logger.error(f"Failed to get pod logs: {e}")
            return []
    
    def collect_pod_describe(self, pod_name: str) -> Dict[str, Any]:
        """
        Collect pod describe information.
        
        Args:
            pod_name: Name of the pod
            
        Returns:
            PodDescribe model with describe output
        """
        logger.info(f"Collecting describe info for pod: {pod_name}")
        
        try:
            pod = self.v1.read_namespaced_pod(name=pod_name, namespace=self.namespace)
            
            # Build describe-like output
            describe_lines = []
            describe_lines.append(f"Name: {pod.metadata.name}")
            describe_lines.append(f"Namespace: {pod.metadata.namespace}")
            describe_lines.append(f"Node: {pod.spec.node_name}")
            describe_lines.append(f"Status: {pod.status.phase}")
            describe_lines.append(f"IP: {pod.status.pod_ip}")
            describe_lines.append("")
            
            # Conditions
            describe_lines.append("Conditions:")
            conditions_list = []
            for condition in (pod.status.conditions or []):
                line = f"  {condition.type}: {condition.status}"
                if condition.reason:
                    line += f" (Reason: {condition.reason})"
                describe_lines.append(line)
                conditions_list.append(line)
            describe_lines.append("")
            
            # Containers
            describe_lines.append("Containers:")
            for cs in (pod.status.container_statuses or []):
                describe_lines.append(f"  {cs.name}:")
                describe_lines.append(f"    Ready: {cs.ready}")
                describe_lines.append(f"    Restart Count: {cs.restart_count}")
                
                if cs.state.running:
                    describe_lines.append(f"    State: Running (started at {cs.state.running.started_at})")
                elif cs.state.waiting:
                    describe_lines.append(f"    State: Waiting")
                    describe_lines.append(f"    Reason: {cs.state.waiting.reason}")
                elif cs.state.terminated:
                    describe_lines.append(f"    State: Terminated")
                    describe_lines.append(f"    Reason: {cs.state.terminated.reason}")
                    describe_lines.append(f"    Exit Code: {cs.state.terminated.exit_code}")
            
            raw_output = "\n".join(describe_lines)
            
            # Get events for this pod
            events_output = []
            field_selector = f"involvedObject.name={pod_name}"
            events_list = self.v1.list_namespaced_event(
                namespace=self.namespace,
                field_selector=field_selector
            )
            
            for event in events_list.items[-10:]:  # Last 10 events
                events_output.append(
                    f"{event.type}: {event.reason} - {event.message} "
                    f"(count: {event.count}, last: {event.last_timestamp})"
                )
            
            return {
                "raw_output": raw_output,
                "events": events_output,
                "conditions": conditions_list
            }
            
        except ApiException as e:
            logger.error(f"Failed to describe pod: {e}")
            raise RuntimeError(f"Failed to describe pod: {e}")
    
    def collect_all_signals(self, pod_name: str) -> Dict[str, Any]:
        """
        Collect all Kubernetes signals for a pod.
        
        Args:
            pod_name: Name of the pod
            
        Returns:
            KubernetesSignals with all collected data
        """
        logger.info(f"Collecting all signals for pod: {pod_name}")
        
        # Collect all signals
        pod_status = self.collect_pod_status(pod_name)
        pod_events = self.collect_pod_events(pod_name)
        pod_logs = self.collect_pod_logs(pod_name)
        pod_describe = self.collect_pod_describe(pod_name)
        
        signals = {
            "pod_status": pod_status,
            "pod_events": pod_events,
            "pod_logs": pod_logs,
            "pod_describe": pod_describe,
            "collected_at": datetime.now(timezone.utc)
        }
        
        logger.info(f"Successfully collected all signals for pod: {pod_name}")
        return signals
