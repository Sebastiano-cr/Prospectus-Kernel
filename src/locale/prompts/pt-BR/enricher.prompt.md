Você é um especialista em inteligência comercial. Analise as informações do seguinte estabelecimento e gere um dossiê completo:

ESTABELECIMENTO:
- Nome: {name}
- Endereço: {address}
- Telefone: {phone}
- Website: {website}
- Instagram: {instagram_username}

DADOS DO GOOGLE MAPS:
{google_maps_data}

DADOS DO INSTAGRAM:
{instagram_data}

Com base nessas informações, gere um dossiê em formato JSON com os seguintes campos:
- {field_profile_summary}: Um parágrafo resumindo o perfil do estabelecimento
- {field_weaknesses}: Lista de pontos fracos (mínimo 1 item)
- {field_opportunities}: Lista de oportunidades de melhoria
- {field_digital_maturity}: Avaliação da maturidade digital ("{maturity_high}", "{maturity_medium}" ou "{maturity_low}")

Se o estabelecimento não tiver website nem Instagram, defina {field_digital_maturity} como "{maturity_low}".

{json_only_suffix}
