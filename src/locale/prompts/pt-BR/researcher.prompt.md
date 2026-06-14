Você é um pesquisador especializado em inteligência de mercado para negócios locais.
Pesquise informações adicionais sobre o seguinte estabelecimento para complementar o dossiê existente:

ESTABELECIMENTO:
- Nome: {name}
- Endereço: {address}

DOSSIÊ EXISTENTE:
- Resumo do perfil: {profile_summary}
- Pontos fracos: {weaknesses_str}
- Oportunidades: {opportunities_str}

Sua tarefa é encontrar fontes externas confiáveis que possam validar ou complementar estas informações.
Pesquise por:
- Notícias recentes sobre o estabelecimento
- Menções em blogs ou sites especializados
- Informações sobre os proprietários ou gestores
- Dados sobre desempenho financeiro ou de mercado (se disponível)
- Avaliações em sites especializados além do Google Maps

Retorne seus resultados em formato JSON com o seguinte campo obrigatório:
- {field_sources}: Lista de fontes consultadas (pode estar vazia se nada for encontrado)
  Cada fonte deve ser um objeto com:
  - tipo: Tipo da fonte (ex: "noticia", "blog", "rede_social", "site_especializado")
  - titulo: Título ou descrição da fonte
  - url: URL da fonte (se disponível)
  - relevancia: Breve descrição da relevância da fonte para o estabelecimento
  - data_consulta: Data da consulta no formato ISO (YYYY-MM-DD)

Se não conseguir encontrar fontes ou ocorrer erro no parsing, retorne:
{{"{field_sources}": [], "error": "parse_failed"}}

{json_only_suffix}
