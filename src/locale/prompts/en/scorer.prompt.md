You are a lead scoring specialist. Evaluate the following establishment's dossier and assign a score from 0 to 100:

{memory_block}

DOSSIER:
- Profile summary: {profile_summary}
- Weaknesses:
{weaknesses_str}
- Opportunities:
{opportunities_str}
- Digital maturity: {digital_maturity}

Based on this information, assign a score from 0 to 100 where:
- 0-39: Lead {cold} (low conversion probability)
- 40-69: Lead {warm} (medium conversion probability)
- 70-100: Lead {hot} (high conversion probability)

Provide your response in JSON format with the following fields:
- score: Integer between 0 and 100
- justification: Score justification with 3-5 sentences
- faixa: Classification as "{cold}", "{warm}" or "{hot}" (based on the score)

{json_only_suffix}
