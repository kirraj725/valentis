"""
LLM Summarizer — Anthropic-powered revenue integrity insights.

Groups flagged anomalies by provider, constructs structured prompts,
and generates actionable plain-English summaries per provider.
Handles context management by batching to stay within token limits.
"""

import os
from datetime import datetime, timezone

ANTHROPIC_AVAILABLE = True
try:
    import anthropic
except ImportError:
    ANTHROPIC_AVAILABLE = False


def _build_provider_prompt(provider_id: str, flags: list[dict]) -> str:
    """Build a structured prompt for a single provider's anomaly batch."""
    flag_lines = []
    for f in flags[:50]:  # Cap at 50 per provider to manage context
        flag_lines.append(
            f"  - Claim {f['claim_id']}: score={f['anomaly_score']:.3f}, "
            f"reason=\"{f['flag_reason']}\""
        )

    return f"""You are a healthcare revenue integrity analyst AI. Analyze the following flagged billing anomalies for Provider {provider_id} and generate a concise, actionable summary.

Provider: {provider_id}
Total flagged claims: {len(flags)}
Anomaly details:
{chr(10).join(flag_lines)}

Generate a single paragraph that:
1. Identifies the dominant pattern(s) in this provider's flagged claims
2. Highlights specific concerns that warrant human review
3. Estimates potential revenue impact if these are true anomalies
4. Recommends concrete next steps for the revenue integrity team

Keep your response to 3-5 sentences. Be specific and data-driven. Do not use bullet points."""


def generate_summaries(
    grouped_flags: dict[str, list[dict]],
    api_key: str | None = None,
) -> list[dict]:
    """
    Generate AI summaries for each provider's anomaly batch.

    Args:
        grouped_flags: Dict of provider_id -> list of flag dicts
        api_key: Anthropic API key (falls back to env var)

    Returns:
        List of summary dicts with provider_id, summary text, and metadata.
    """
    key = api_key or os.getenv("ANTHROPIC_API_KEY")

    if not key or not ANTHROPIC_AVAILABLE:
        # Fallback: generate rule-based summaries when API unavailable
        return _generate_fallback_summaries(grouped_flags)

    client = anthropic.Anthropic(api_key=key)
    summaries = []

    for provider_id, flags in grouped_flags.items():
        prompt = _build_provider_prompt(provider_id, flags)

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            summary_text = response.content[0].text
        except Exception as e:
            summary_text = (
                f"Unable to generate AI summary for {provider_id}: {str(e)}. "
                f"This provider has {len(flags)} flagged claims requiring manual review."
            )

        avg_score = sum(f["anomaly_score"] for f in flags) / len(flags)
        summaries.append({
            "provider_id": provider_id,
            "summary": summary_text,
            "claim_count": len(flags),
            "avg_anomaly_score": round(avg_score, 4),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "anthropic",
            "disclaimer": "AI-generated insight for human review — not an automated decision.",
        })

    return summaries


def _generate_fallback_summaries(grouped_flags: dict[str, list[dict]]) -> list[dict]:
    """Generate rule-based summaries when Anthropic API is unavailable."""
    summaries = []

    for provider_id, flags in grouped_flags.items():
        avg_score = sum(f["anomaly_score"] for f in flags) / len(flags)
        reasons = {}
        for f in flags:
            for r in f["flag_reason"].split("; "):
                reasons[r] = reasons.get(r, 0) + 1

        top_reasons = sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:3]
        reason_str = ", ".join(f"{r} ({c} claims)" for r, c in top_reasons)

        severity = "high" if avg_score < -0.2 else "moderate" if avg_score < -0.1 else "low"

        summary = (
            f"Provider {provider_id} has {len(flags)} flagged claims with a {severity} "
            f"average anomaly score of {avg_score:.3f}. "
            f"Primary patterns: {reason_str}. "
            f"These claims warrant human review to determine if billing corrections are needed."
        )

        summaries.append({
            "provider_id": provider_id,
            "summary": summary,
            "claim_count": len(flags),
            "avg_anomaly_score": round(avg_score, 4),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "rule-based",
            "disclaimer": "AI-generated insight for human review — not an automated decision.",
        })

    return summaries
