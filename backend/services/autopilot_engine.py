"""Autopilot engine — autonomous pipeline execution with quality gates."""
import uuid
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Step types for the autopilot pipeline
STEP_TYPES = [
    "research", "plan", "execute", "review", "validate", "deploy", "report"
]

# Default pipeline templates
PIPELINE_TEMPLATES = {
    "feature": {
        "name": "Feature Implementation",
        "steps": [
            {"step_type": "research", "name": "Research & Analysis", "description": "Analyze requirements and existing codebase"},
            {"step_type": "plan", "name": "Implementation Plan", "description": "Create detailed implementation plan"},
            {"step_type": "execute", "name": "Build Feature", "description": "Implement the feature code"},
            {"step_type": "review", "name": "Code Review", "description": "Review for quality, security, and best practices"},
            {"step_type": "validate", "name": "Testing & Validation", "description": "Run tests and validate functionality"},
            {"step_type": "deploy", "name": "Deploy", "description": "Deploy to target environment"},
            {"step_type": "report", "name": "Completion Report", "description": "Generate summary report"},
        ],
        "quality_gates": [
            {"after_step": 2, "check": "plan_completeness", "threshold": 0.8},
            {"after_step": 3, "check": "code_quality", "threshold": 0.7},
            {"after_step": 4, "check": "review_pass", "threshold": 0.9},
        ]
    },
    "bugfix": {
        "name": "Bug Fix Pipeline",
        "steps": [
            {"step_type": "research", "name": "Bug Reproduction", "description": "Reproduce and analyze the bug"},
            {"step_type": "plan", "name": "Root Cause Analysis", "description": "Identify root cause and fix strategy"},
            {"step_type": "execute", "name": "Implement Fix", "description": "Apply the fix"},
            {"step_type": "validate", "name": "Verify Fix", "description": "Verify the fix resolves the issue"},
            {"step_type": "report", "name": "Fix Report", "description": "Document the fix"},
        ],
        "quality_gates": [
            {"after_step": 1, "check": "bug_reproduced", "threshold": 1.0},
            {"after_step": 3, "check": "fix_applied", "threshold": 0.8},
        ]
    },
    "analysis": {
        "name": "Analysis Pipeline",
        "steps": [
            {"step_type": "research", "name": "Data Gathering", "description": "Collect relevant data and context"},
            {"step_type": "execute", "name": "Analysis", "description": "Perform analysis"},
            {"step_type": "report", "name": "Report Generation", "description": "Generate analysis report"},
        ],
        "quality_gates": [
            {"after_step": 1, "check": "data_sufficient", "threshold": 0.7},
        ]
    },
    "custom": {
        "name": "Custom Pipeline",
        "steps": [],
        "quality_gates": []
    }
}


def generate_run_id() -> str:
    return f"ap-{uuid.uuid4().hex[:8]}"


def generate_step_id() -> str:
    return f"aps-{uuid.uuid4().hex[:8]}"


def build_pipeline_steps(template_key: str, objective: str) -> list[dict]:
    """Build steps from a template, injecting the objective."""
    template = PIPELINE_TEMPLATES.get(template_key, PIPELINE_TEMPLATES["custom"])
    steps = []
    for i, step_def in enumerate(template["steps"]):
        step = {
            "id": generate_step_id(),
            "step_type": step_def["step_type"],
            "name": step_def["name"],
            "description": step_def.get("description", ""),
            "status": "pending",
            "config": {"objective": objective},
            "order": i,
        }
        steps.append(step)
    return steps


async def evaluate_quality_gate(gate: dict, step_output: dict | None) -> dict:
    """Evaluate a quality gate check. Returns pass/fail with score."""
    check_type = gate.get("check", "")
    threshold = gate.get("threshold", 0.8)

    # Simulate quality gate evaluation
    # In production, this would call Aegis or actual quality metrics
    score = 0.85  # Default pass score for now

    # Different checks have different evaluation logic
    if check_type in ("review_pass", "code_quality"):
        # These require higher scores
        score = 0.82
    elif check_type == "bug_reproduced":
        score = 1.0
    elif check_type == "plan_completeness":
        score = 0.88
    elif check_type == "fix_applied":
        score = 0.90
    elif check_type == "data_sufficient":
        score = 0.80

    # If step output has a quality_score, use it
    if step_output and "quality_score" in step_output:
        score = step_output["quality_score"]

    passed = score >= threshold
    return {
        "check": check_type,
        "threshold": threshold,
        "score": score,
        "passed": passed,
        "message": f"{'PASS' if passed else 'FAIL'}: {check_type} score {score:.2f} vs threshold {threshold:.2f}"
    }


async def execute_step_with_ai(step: dict, context: dict) -> dict:
    """Execute a single autopilot step using AI. Returns output data."""
    from services.ai_client import ai_client

    step_type = step["step_type"]
    objective = context.get("objective", "")
    step_name = step.get("name", step_type)
    description = step.get("description", "")

    prompt = f"""You are an AI agent executing step "{step_name}" in an autonomous pipeline.

Objective: {objective}
Step Type: {step_type}
Description: {description}

Previous context: {json.dumps(context.get('previous_outputs', {}), indent=2)[:2000]}

Execute this step and provide:
1. A summary of what you did
2. Key findings or outputs
3. A quality score (0-1) for this step's output
4. Any issues or blockers encountered

Respond in JSON format:
{{"summary": "...", "output": {{...}}, "quality_score": 0.85, "issues": []}}"""

    system = f"You are an expert AI agent performing {step_type} tasks. Be thorough and precise. Always respond with valid JSON."

    try:
        result = await ai_client.generate(prompt, system=system)
        # Try to parse as JSON
        try:
            parsed = json.loads(result)
            return {
                "output_data": json.dumps(parsed),
                "quality_score": parsed.get("quality_score", 0.7),
                "summary": parsed.get("summary", ""),
                "issues": parsed.get("issues", []),
            }
        except json.JSONDecodeError:
            return {
                "output_data": json.dumps({"raw": result}),
                "quality_score": 0.7,
                "summary": result[:500],
                "issues": [],
            }
    except Exception as e:
        logger.error(f"Step execution failed: {e}")
        return {
            "output_data": json.dumps({"error": str(e)}),
            "quality_score": 0.0,
            "summary": f"Step failed: {e}",
            "issues": [str(e)],
        }
