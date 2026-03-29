#!/usr/bin/env python3
"""
WeWrite Optimization Loop — autoresearch-style iterative improvement.

Inspired by Karpathy's autoresearch: change → score → keep/rollback → repeat.
But instead of optimizing ML training code, we optimize WRITING RULES to
produce articles that pass AI detection while maintaining quality.

The mutable surface: writing-config.yaml (style parameters + prompt rules)
The fixed evaluation: humanness_score.py (objective checklist + subjective feel)
The metric: composite_score (lower = more human, like val_bpb)

Usage:
    python3 optimize_loop.py --topic "AI Agent" --iterations 10
    python3 optimize_loop.py --topic "AI Agent" --iterations 5 --verbose

Architecture:
    1. Load current writing-config.yaml
    2. Generate article with current config
    3. Score with humanness_score.py
    4. LLM proposes a change to writing-config.yaml
    5. Generate article with new config
    6. Score again
    7. If improved → keep (commit). If not → rollback.
    8. Log to results.tsv
    9. Repeat.

Requirements:
    - ANTHROPIC_API_KEY in environment (for article generation + LLM judge)
    - writing-config.yaml in skill root (created on first run with defaults)
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).parent.parent
CONFIG_PATH = SKILL_DIR / "writing-config.yaml"
RESULTS_PATH = SKILL_DIR / "optimization-results.tsv"

DEFAULT_CONFIG = {
    "persona": "科技媒体资深编辑，写了八年公众号，对AI行业有深度认知",
    "sentence_variance": 0.7,
    "broken_sentence_rate": 0.04,
    "idiom_density": 0.15,
    "filler_style": "mixed",  # literary / casual / mixed / minimal
    "paragraph_rhythm": "chaotic",  # structured / chaotic / wave
    "self_correction_rate": 0.02,
    "tangent_frequency": "every_800_chars",  # never / every_500 / every_800 / every_1200
    "real_data_density": "high",  # low / medium / high
    "word_temperature_bias": "warm",  # cold / warm / hot / balanced
    "emotional_arc": "restrained_to_burst",  # flat / gradual / restrained_to_burst / volatile
    "opening_style": "scene",  # scene / data / question / anecdote / cold_open
    "closing_style": "open_question",  # summary / open_question / image / abrupt
    "structure_linearity": 0.3,  # 0=fully non-linear, 1=fully linear
}


def ensure_config():
    """Create default writing-config.yaml if it doesn't exist."""
    if not CONFIG_PATH.exists():
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, default_flow_style=False)
        print(f"Created default config: {CONFIG_PATH}")
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def score_article(article_path: str) -> dict:
    """Run humanness_score.py on an article. Returns parsed result."""
    result = subprocess.run(
        ["python3", str(SKILL_DIR / "scripts" / "humanness_score.py"), article_path, "--json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Scoring failed: {result.stderr}", file=sys.stderr)
        return {"composite_score": 100.0, "error": result.stderr}
    return json.loads(result.stdout)


def log_result(iteration: int, composite: float, config_summary: str, status: str, description: str):
    """Append result to TSV log."""
    header_needed = not RESULTS_PATH.exists()
    with open(RESULTS_PATH, "a", encoding="utf-8") as f:
        if header_needed:
            f.write("iteration\ttimestamp\tcomposite\tstatus\tdescription\tconfig_change\n")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{iteration}\t{ts}\t{composite:.2f}\t{status}\t{description}\t{config_summary}\n")


def print_banner(iteration: int, total: int):
    print(f"\n{'='*60}")
    print(f"  OPTIMIZATION LOOP — Iteration {iteration}/{total}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="WeWrite optimization loop")
    parser.add_argument("--topic", required=True, help="Article topic for testing")
    parser.add_argument("--iterations", type=int, default=10, help="Number of iterations")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════╗
║  WeWrite Optimization Loop                          ║
║  Topic: {args.topic:<44s}║
║  Iterations: {args.iterations:<39d}║
║                                                      ║
║  Pattern: change config → generate → score →         ║
║           keep if better, rollback if worse           ║
╚══════════════════════════════════════════════════════╝
""")

    config = ensure_config()

    print("This script provides the FRAMEWORK for optimization.")
    print("To run the full loop, you need:")
    print("  1. An article generation function (Claude API)")
    print("  2. A scoring function (humanness_score.py — included)")
    print("  3. An LLM to propose config changes (Claude API)")
    print()
    print("Current config:")
    print(yaml.dump(config, allow_unicode=True, default_flow_style=False))
    print()
    print("Run this loop via Claude Code / OpenClaw agent:")
    print()
    print("  Agent reads writing-config.yaml")
    print("  → generates article with those rules")
    print("  → scores with: python3 scripts/humanness_score.py article.md --json")
    print("  → proposes a config change")
    print("  → generates new article")
    print("  → scores again")
    print("  → if composite_score decreased → commit config change")
    print("  → if composite_score same/worse → rollback")
    print("  → logs to optimization-results.tsv")
    print("  → repeats")
    print()
    print("To test scoring on an existing article:")
    print(f"  python3 scripts/humanness_score.py <article.md> --verbose")


if __name__ == "__main__":
    main()
