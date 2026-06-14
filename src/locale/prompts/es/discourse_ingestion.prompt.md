You are an expert analyst of online market discourse. Your task is to
normalize a raw piece of discourse into a structured schema.

Analyze the following discourse fragment from {source}. Normalize it,
detect the surface emotion, classify the topic, and provide surrounding
context if not given. Interpret the text by its social use — what language
game is being played?

FRAGMENT TEXT:
{repr(text)}

SOURCE PLATFORM: {source}

{context_block}

---

Instructions:
1. Return the text exactly as provided (do not paraphrase or summarize).
2. Return the source platform as given.
3. If context was not provided, infer the most likely conversational
   context from the text and source. Leave empty only if truly
   impossible to infer.
4. Detect the SURFACE-LEVEL emotion (the overt affective signal).
   Examples: frustration, excitement, confusion, anger, hope, skepticism,
   relief, anxiety, pride, disappointment.
5. Classify the TOPIC into one concise category. Examples: pricing,
   onboarding, feature_request, competitor_comparison, hiring,
   content_creation, sales_process, tool_selection, market_fit,
   scaling, burnout.

Output a JSON object with exactly these fields:
{{
  "text": "<exact raw text>",
  "source": "<platform>",
  "context": "<inferred or provided context>",
  "emotion": "<surface emotion>",
  "topic": "<topic classification>"
}}

{json_only_suffix}
