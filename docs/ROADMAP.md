# Roadmap

## v0.1 Alpha — entregue para validação no Windows
- [x] Aplicativo Windows Tkinter, modo Demo sem simulador.
- [x] Integração opcional SimConnect somente leitura com 8 SimVars (7 essenciais exibidas, 1 para estado de solo; mais 2 opcionais: combustível/estol).
- [x] Detector de voo por estado do solo, com anti-bounce e estimativa de razão vertical no toque.
- [x] Diário local persistente SQLite, uma carreira independente.
- [x] Três contratos iniciais em Pernambuco e Paraíba, com validação de origem e destino e recompensa única.
- [x] Inspetor somente leitura que faz cópia de common.db e extrai apenas estrutura SQLite.
- [x] Testes independentes de MSFS e ação CI.
- [x] Demo e conexão SimConnect ao MSFS 2020 confirmadas pelo piloto no Windows.
- [x] Inspeção do esquema real do NeoFly: relatório SQLite analisado (54 tabelas, apenas metadados de estrutura).\n- [ ] Implementar prévia de importação local e somente leitura, sem duplicidade nem alteração dos dados originais.\n- [ ] Validar uma missão completa no MSFS real (decolagem, voo, pouso, recompensa, diário).

## v0.1.1 — após teste físico
- Robustez de conexão e reconexão de SimConnect, frequência, dados nulos.
- Registro de múltiplos voos por sessão sem falso positivo em toques sucessivos.
- Atividade e logs de erro mais detalhados.
- Indicadores de combustível, aeronave, luzes, avisos de estol, arremetida.
- Refinamento de avaliação da aproximação e pouso para não incentivar comportamentos inseguros.

## v0.2 — fundação de carreira
- Importação opcional de campos de progresso do NeoFly após estudo de compatibilidade; nunca sobrescrever original.
- Cadastro de aeronaves, manutenção, abastecimento e seguro.
- Missões geradas a partir de catálogo licenciado de aeroportos, objetivos e regras realistas.
- Contratos diferenciados: turismo, carga, táxi aéreo.
- Progressão financeira, habilitações e reputação.

## Painel integrado ao MSFS 2020 — REQUISITO PRIORITÁRIO\n- [ ] Interface integral na toolbar do MSFS 2020, **sem Alt+Tab** para mapa, contratos, pagamentos, frota ou diário.\n- [ ] Motor Windows/SimConnect em segundo plano, API/WS apenas loopback e autenticada para ações mutáveis.\n- [ ] PoC de package Community com painel e telemetria, validada no MSFS 2020 Steam.\n- [ ] Mapa navegável e contratos operacionais na interface in-game.\n- [ ] Inicialização automática do companion e recuperação de conexão sem intervenção externa.\n- [ ] Testes de regressão e validação de UI/ponte real.\n- [ ] Consultar [arquitetura in-game](ARQUITETURA_IN_GAME.md) e [esquema NeoFly](NEOFLY_SCHEMA.md).\n\n## v0.3+
- Histórias de voos e eventos narrativos originais.
- Companhia aérea, equipe, frota, empresas e contratos extensos.
- Pacote de instalação Windows em exe assinado, quando a arquitetura for estabilizada.
