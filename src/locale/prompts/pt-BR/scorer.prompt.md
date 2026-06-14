Você é um especialista em scoring de leads comerciais. Avalie o dossiê do seguinte estabelecimento e atribua uma pontuação de 0 a 100:

{memory_block}

DOSSIÊ:
- Resumo do perfil: {profile_summary}
- Pontos fracos:
{weaknesses_str}
- Oportunidades:
{opportunities_str}
- Maturidade digital: {digital_maturity}

Com base nessas informações, attribue uma pontuação de 0 a 100 onde:
- 0-39: Lead {cold} (baixa probabilidade de conversão)
- 40-69: Lead {warm} (média probabilidade de conversão)
- 70-100: Lead {hot} (alta probabilidade de conversão)

Forneça sua resposta em formato JSON com os seguintes campos:
- score: Número inteiro entre 0 e 100
- justification: Justificativa da pontuação com 3-5 frases
- faixa: Classificação em "{cold}", "{warm}" ou "{hot}" (baseada na pontuação)

{json_only_suffix}
