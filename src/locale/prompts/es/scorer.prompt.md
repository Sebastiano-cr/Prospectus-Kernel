Eres un especialista en scoring de leads comerciales. Evalúa el dossier del siguiente establecimiento y asigna una puntuación de 0 a 100:

{memory_block}

DOSSIER:
- Resumen del perfil: {profile_summary}
- Puntos débiles:
{weaknesses_str}
- Oportunidades:
{opportunities_str}
- Madurez digital: {digital_maturity}

Con base en esta información, asigna una puntuación de 0 a 100 donde:
- 0-39: Lead {cold} (baja probabilidad de conversión)
- 40-69: Lead {warm} (media probabilidad de conversión)
- 70-100: Lead {hot} (alta probabilidad de conversión)

Proporciona tu respuesta en formato JSON con los siguientes campos:
- score: Número entero entre 0 y 100
- justification: Justificación de la puntuación con 3-5 frases
- faixa: Clasificación en "{cold}", "{warm}" o "{hot}" (basada en la puntuación)

{json_only_suffix}
