"""Event names padronizados em português brasileiro para logging estruturado."""

from __future__ import annotations


class LogEvents:
    """Constantes de event names para logs do BotSalinha.

    Todos os event names são em português brasileiro para consistência.
    Use estas constantes em vez de strings literais para evitar typos.
    """

    # Aplicação
    APP_INICIADA = "aplicacao_iniciada"
    APP_PARADA = "aplicacao_parada"

    # Bot Discord
    BOT_DISCORD_INICIALIZADO = "bot_discord_inicializado"
    BOT_PRONTO_SEM_USUARIO = "bot_pronto_sem_usuario"
    CANAL_IA_ID_MALFORMADO = "canal_ia_id_malformado"

    # Comandos
    COMANDO_ERRO = "comando_erro"
    COMANDO_ASK_CONCLUIDO = "comando_ask_concluido"
    COMANDO_ASK_FALHOU = "comando_ask_falhou"
    COMANDO_LIMPAR_INICIADO = "comando_limpar_iniciado"
    COMANDO_LIMPAR_SUCESSO = "comando_limpar_sucesso"
    COMANDO_LIMPAR_SEM_CONVERSA = "comando_limpar_sem_conversa"

    # Agente IA
    AGENTE_INICIALIZADO = "agente_inicializado"
    AGENTE_GERANDO_RESPOSTA = "agente_gerando_resposta"
    AGENTE_RESPOSTA_GERADA = "agente_resposta_gerada"
    AGENTE_GERACAO_FALHOU = "agente_geracao_falhou"

    # Banco de Dados
    BANCO_DADOS_INICIALIZADO = "banco_dados_inicializado"
    BANCO_DADOS_LIMPO = "banco_dados_limpo"
    TABELAS_BANCO_CRIADAS = "tabelas_banco_criadas"
    MODO_WAL_ATIVADO = "modo_wal_ativado"
    CONVERSAS_ANTIGAS_LIMPAS = "conversas_antigas_limpas"

    # Repositório
    REPOSITORIO_SQLITE_INICIALIZADO = "repositorio_sqlite_inicializado"
    REPOSITORIO_SQLITE_FECHADO = "repositorio_sqlite_fechado"

    # Rate Limiter
    LIMITE_TAXA_ACIONADO = "limite_taxa_acionado"
    LIMITE_TAXA_LIMPEZA = "limite_taxa_limpeza"
    LIMITE_TAXA_REINICIADO = "limite_taxa_reiniciado"
    LIMITE_TAXA_REINICIADO_TODOS = "limite_taxa_reiniciado_todos"

    # API
    API_ERRO_GERAR_RESPOSTA = "api_erro_gerar_resposta"

    # Usuário
    USUARIO_BLOQUEOU_BOT = "usuario_bloqueou_bot"
    MENSAGEM_PROCESSADA = "mensagem_processada"
    ERRO_INESPERADO_PROCESSAR_MENSAGEM = "erro_inesperado_processar_mensagem"

    # Lifecycle
    TAREFA_LIMPEZA_REGISTRADA = "tarefa_limpeza_registrada"
    MANIPULADORES_SINAIS_CONFIGURADOS = "manipuladores_sinais_configurados"
    SINAL_RECEBIDO = "sinal_recebido"
    SAIDA_FORCADA_ACIONADA = "saida_forcada_acionada"
    DESLIGAMENTO_INICIADO = "desligamento_iniciado"
    LIMPEZA_INICIADA = "limpeza_iniciada"
    EXECUTANDO_TAREFA_LIMPEZA = "executando_tarefa_limpeza"
    TAREFA_LIMPEZA_FALHOU = "tarefa_limpeza_falhou"
    LIMPEZA_MCP_TRATADA_POR_AGENTE = "limpeza_mcp_tratada_por_agente"
    LIMPEZA_CONCLUIDA = "limpeza_concluida"

    # Configuração
    CONFIG_YAML_NAO_ENCONTRADO = "config_yaml_nao_encontrado"
    ERRO_PARSEAR_CONFIG_YAML = "erro_parsear_config_yaml"
    CONFIG_YAML_VAZIO = "config_yaml_vazio"
    VALIDACAO_CONFIG_YAML_FALHOU = "validacao_config_yaml_falhou"
    CONFIG_YAML_CARREGADO = "config_yaml_carregado"

    # MCP
    FERRAMENTAS_MCP_ANEXADAS = "ferramentas_mcp_anexadas"
    FERRAMENTAS_MCP_NAO_LISTA = "ferramentas_mcp_nao_lista"
    SERVIDOR_MCP_ENV_VAZIO = "servidor_mcp_env_vazio"

    # Circuit Breaker
    DISJUNTOR_ABERTO = "disjuntor_aberto"

    # RAG (Retrieval-Augmented Generation)
    RAG_CHUNKS_CRIADOS = "rag_chunks_criados"
    RAG_BUSCA_INICIADA = "rag_busca_iniciada"
    RAG_BUSCA_CONCLUIDA = "rag_busca_concluida"
    RAG_CONFIDENCE_CALCULADA = "rag_confidence_calculada"


__all__ = ["LogEvents"]
