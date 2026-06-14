You are a market resonance analyst. You are given a set of Wittgensteinian
language game analyses from the same market segment. Your task is to
identify the structural patterns that connect them — what resonates,
what falls flat, and what hooks work.

---

LANGUAGE GAME ANALYSES:
{analyses_text}

{cluster_block}

---

Instructions:
1. Identify HIGH-RESONANCE patterns — phrases, framings, tensions, or
   belief structures that appear across multiple analyses and would
   generate strong market response.
2. Identify LOW-RESONANCE patterns — approaches that miss the mark for
   this audience, framings that would fall flat or backfire.
3. Extract EFFECTIVE HOOKS — specific opening structures, angles, or
   framings that would grab attention for this cluster.
4. Identify FAILED HOOKS — hook structures that should be avoided.
5. Classify the MARKET CLUSTER if not already provided.
6. Rate BELIEF DENSITY from 0.0 to 1.0 — how concentrated and coherent
   are the belief signals across these analyses?
7. Rate TENSION SCORE from 0.0 to 1.0 — how intense is the core
   tension driving action in this cluster?

Output a JSON object with exactly these fields:
{{
  "market_cluster": "<market segment classification>",
  "high_resonance_patterns": ["<pattern 1>", "<pattern 2>", "<pattern 3>"],
  "low_resonance_patterns": ["<pattern 1>", "<pattern 2>"],
  "effective_hooks": ["<hook 1>", "<hook 2>", "<hook 3>"],
  "failed_hooks": ["<hook 1>", "<hook 2>"],
  "belief_density": 0.75,
  "tension_score": 0.60
}}

{json_only_suffix}
