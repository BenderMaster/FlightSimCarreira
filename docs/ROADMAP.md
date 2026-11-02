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
- [x] Inspeção do esquema real do NeoFly: relatório SQLite (54 tabelas, sem registros pessoais).

## v0.1.2 — falha de conexão em voo: patch entregue para validação física
- [x] Proteger a sessão de perdas pontuais de `GROUND_VELOCITY` / `VERTICAL_SPEED`.
- [x] Reconectar automaticamente em caso de queda persistente de SimConnect.
- [x] Checkpoint de missão/voo e retomada após reinício do app.
- [x] Pouso+crédito atômico sem recompensa duplicada; migração do SQLite anterior.
- [x] Rota SIPE → SIFC para teste rápido; testes automatizados e interface virtual aprovados.
- [x] Validar voo real SIPE → SIFC no MSFS 2020: decolagem 19:45:14, pouso 19:55:07, razão estimada −172 ft/min, $420 creditados, saldo $6.270 e contrato encerrado (evidência: captura enviada pelo piloto em 02/11/2026).
- [ ] Validar **reconexão automática após perda real de SimConnect em voo**; a captura do pouso comprova conexão ao final, mas não necessariamente recuperação após interrupção.
- [ ] Validar persistência e ausência de crédito duplicado ao fechar/reabrir o aplicativo após pouso real.

## v0.1.3 — melhorias após teste físico
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

## v0.3+
- Histórias de voos e eventos narrativos originais.
- Companhia aérea, equipe, frota, empresas e contratos extensos.
- Pacote de instalação Windows em exe assinado, quando a arquitetura for estabilizada.

## Requisito prioritário: interface dentro do MSFS 2020
- [ ] Painel de toolbar dentro do simulador para mapa, contratos, diário de bordo e frota; sem Alt+Tab.
- [ ] Ponte local testada e package Community. Veja [arquitetura in-game](ARQUITETURA_IN_GAME.md).
