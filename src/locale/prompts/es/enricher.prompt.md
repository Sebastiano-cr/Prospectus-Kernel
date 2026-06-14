Eres un especialista en inteligencia comercial. Analiza la información del siguiente establecimiento y genera un dossier completo:

ESTABLECIMIENTO:
- Nombre: {name}
- Dirección: {address}
- Teléfono: {phone}
- Sitio web: {website}
- Instagram: {instagram_username}

DATOS DE GOOGLE MAPS:
{google_maps_data}

DATOS DE INSTAGRAM:
{instagram_data}

Con base en esta información, genera un dossier en formato JSON con los siguientes campos:
- {field_profile_summary}: Un párrafo resumiendo el perfil del establecimiento
- {field_weaknesses}: Lista de puntos débiles (mínimo 1 elemento)
- {field_opportunities}: Lista de oportunidades de mejora
- {field_digital_maturity}: Evaluación de la madurez digital ("{maturity_high}", "{maturity_medium}" o "{maturity_low}")

Si el establecimiento no tiene sitio web ni Instagram, define {field_digital_maturity} como "{maturity_low}".

{json_only_suffix}
