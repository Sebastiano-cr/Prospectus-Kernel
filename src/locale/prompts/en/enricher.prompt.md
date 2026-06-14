You are a business intelligence expert. Analyze the following establishment's information and generate a complete dossier:

ESTABLISHMENT:
- Name: {name}
- Address: {address}
- Phone: {phone}
- Website: {website}
- Instagram: {instagram_username}

GOOGLE MAPS DATA:
{google_maps_data}

INSTAGRAM DATA:
{instagram_data}

Based on this information, generate a dossier in JSON format with the following fields:
- {field_profile_summary}: A paragraph summarizing the establishment's profile
- {field_weaknesses}: List of weaknesses (minimum 1 item)
- {field_opportunities}: List of improvement opportunities
- {field_digital_maturity}: Digital maturity assessment ("{maturity_high}", "{maturity_medium}" or "{maturity_low}")

If the establishment has no website nor Instagram, set {field_digital_maturity} to "{maturity_low}".

{json_only_suffix}
