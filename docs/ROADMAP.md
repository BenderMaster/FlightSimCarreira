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
- [x] Validar voo real SIPE → SIFC, pouso e crédito de $420 no MSFS 2020; saldo persistiu ao reabrir.
- [ ] Validar reconexão automática após queda real de SimConnect em voo.

## v0.1.3 — melhorias após teste físico
- Robustez de conexão e reconexão de SimConnect, frequência, dados nulos.
- Registro de múltiplos voos por sessão sem falso positivo em toques sucessivos.
- Atividade e logs de erro mais detalhados.
- Indicadores de combustível, aeronave, luzes, avisos de estol, arremetida.
- Refinamento de avaliação da aproximação e pouso para não incentivar comportamentos inseguros.

## v0.2.0-alpha.1 — Bloco 1: piloto e habilitações
- [x] Cadastro/edição de piloto virtual, indicativo e base ICAO.
- [x] Pontuação de XP atômica por voo concluído; requisitos e pré-requisitos de habilitações virtuais.
- [x] UI Meu piloto / Habilitações, migração aditiva de dados e testes automatizados.
- [ ] Validar UI e progressão no Windows real com o piloto.
- [ ] Alinhar requisitos realistas de cursos/provas antes de bloquear contratos e aeronaves.
- [x] Documentar escopo completo e opções futuras (falhas configuráveis, tráfego multiplayer, pinturas e companhias).

## v0.3.0-alpha.1 — Bloco 2: contratos e freelance
- [x] Nível do piloto derivado de XP, independente das habilitações; progressão balanceável.
- [x] Contratos com 9 tipos, restrições de nível, habilitação e horas.
- [x] Geração local por aeroportos do entorno; até 10 regionais + 3 freelancer, 1 origem ativa no banco, duração 1 dia UTC.
- [x] Base `airportsdata` MIT opcional via pip; fallback local e aviso ao piloto, sem usar dados do NeoFly.
- [x] Freelancer com aeronave designada pelo contratante, remuneração sem compra ou aluguel pelo piloto, experiência por modelo/família.
- [x] Validação de modelo na decolagem e no pouso; nenhuma recompensa se não houver confirmação.
- [x] Checkpoint de contrato dinâmico, pagamento único no SQLite e preservação de todos os registros antigos.
- [x] Tela de mercado e 49 testes automatizados + teste visual em ambiente virtual.
- [ ] Testar leitura TITLE do SimConnect e catalogação mundial no Windows/MSFS real.
- [ ] Mecânicas específicas de cada categoria (resgate, ambulância, passageiros, turismo, objetivos temporizados).
- [ ] Aeronaves fornecidas automaticamente por empresa/frota, e comprovação de propriedade, após gestão de frota e pesquisa SDK.
- [ ] Painel de toolbar in-game (requisito transversal).

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

Escopo completo em [ESCOPO_CARREIRA.md](ESCOPO_CARREIRA.md).
