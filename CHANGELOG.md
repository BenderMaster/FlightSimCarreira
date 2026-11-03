# Changelog

## 0.4.0-alpha.2 — correção de backup no Windows (02/11/2026)
- Fechamento explícito do handle da conexão SQLite de backup após a cópia, evitando `WinError 32` no runner Windows.
- Sem alterações de funcionalidade no domínio; mantém Bloco 3 e a interface da Alpha.1.

## 0.4.0-alpha.1 — modalidades de carreira e plano VFR (02/11/2026)
- Nova modalidade `autonomo` por padrão, `empregado` após seleção semanal, e `empresario` como registro inicial de companhia no endgame.
- Catálogo limitado de quatro vagas semanais **fictícias**, com empresas de referência e validação de nível/horas/habilitações; uma candidatura por semana, resultado após o ciclo, sem duplicidades.
- Trechos regionais para piloto contratado, com modelo obrigatório e pagamento único; não existe pagamento periódico de salário sem voar nesta Alpha.
- Acesso ao registro de empresa própria no endgame, com dedução única e sem gestão operacional nesta versão.
- Exportação de `.PLN` VFR e comando explícito para carregar no MSFS 2020 em solo pela biblioteca SimConnect; não troca aeronave. Integração ainda depende de teste no MSFS real.
- Migração SQLite aditiva, testes de regressão e documentação de futura frota IA/liveries.


## 0.3.0-alpha.1 — Bloco 2: contratos regionais e freelancer (02/11/2026)
- 9 categorias de missão com níveis de desbloqueio, horas e qualificações (PPA/PCA/IFR/MLTE/PLA); progressão XP → nível sem perda de dados anteriores.
- Catálogo mundial opcional fornecido pela dependência MIT `airportsdata==2026.8.2`, com fallback local. Não gerar ofertas do mundo inteiro: no máximo 13 contratos perto da origem atual.
- Mercado por aeroporto-base/posição atual, propostas determinísticas por dia, cache local SQLite com vencimento e limpeza por região.
- Freelancer com salário e aeronave de contratante (C152/C172/G58/King Air/CJ4), escolhida manualmente no MSFS até integração futura; validação de modelo na decolagem e no pouso.
- Experiência por família/modelo da aeronave em novos voos, sem inventar XP ou aeronave dos voos antigos.
- Checkpoint preserva missões dinâmicas durante reconexão/reinício; bloqueio transacional de pagamentos repetidos por contrato e por voo.
- Tela dedicada ao mercado com seleção de proposta e detalhes; contratos fixos anteriores mantidos para testes e regressão.
- Migração SQLite aditiva, sem apagar piloto, habilitações, XP, saldo ($6.270 registrado pelo usuário), histórico ou checkpoint.
- **49 testes automatizados locais e teste gráfico do mercado aprovados.** A geração global e a leitura TITLE pelo SimConnect real ainda precisam ser verificadas no Windows.
- Limitações: variantes de missão têm a mesma conclusão básica por chegada ao destino; freelancer não injeta uma aeronave no simulador nem valida tail number/propriedade. Painel MSFS in-game segue prioridade transversal.


## 0.2.0-alpha.1 — Bloco 1: Piloto e habilitações (02/11/2026)
- Cadastro e edição de piloto único por carreira: nome, indicativo e base ICAO.
- Painel próprio de piloto com progressão virtual, horas de voo, XP e cursos PPA/PCA/IFR/MLTE/PLA.
- XP por novos voos finalizados após criação do perfil: 25 por voo + 15 por contrato pago, atômico com o voo e sem duplicidade.
- Migração aditiva SQLite preserva saldo, histórico e checkpoint. Voos anteriores contam nas estatísticas, sem XP retroativo.
- Habilitações por pré-requisito (voos, XP e etapas anteriores); contratos existentes permanecem acessíveis.
- Requisitos adicionais (falhas opcionais, mapa in-game, multiplayer, companhias e pinturas) no documento de escopo.
- 34 testes automatizados locais aprovados e teste gráfico de criação/reabertura de perfil em ambiente virtual.
- **Ainda sem teste físico no Windows da nova UI; sem restrições de contratos por qualificação neste bloco.**

## Validação física v0.1.2 (02/11/2026)
- Voo real SIPE → SIFC completo: decolagem 19:45:14, pouso 19:55:07, −172 ft/min estimados, crédito de $420 e saldo $6.270.
- O piloto confirmou que, ao reabrir o programa, o saldo persistiu. Reconexão após falha real durante voo ainda pendente de teste específico.

## 0.1.2-alpha — patch telemetria e recuperação (02/11/2026)
- Corrigida desconexão fatal por `GROUND_VELOCITY` ausente em única leitura.
- Leitura degradada de velocidade de solo e razão vertical; perda de variável essencial causa descarte temporário, com reconexão após falhas consecutivas.
- Worker com reconexão automática em caso de sessão SimConnect quebrada; mensagens por geração evitam eventos de sessões antigas.
- Checkpoint de contrato/voo durante o voo, recuperado ao reabrir o aplicativo.
- Gravação atômica de diário e crédito com identidade única por decolagem; migração compatível com `carreira.db` anterior.
- Nova rota curta SIPE → SIFC (Coroa do Avião / Igarassu), recompensa de $420.
- Botão Salvar log para diagnóstico; UI informa `~` em velocidades de solo estimadas.
- Testes novos de regressão para falha de SimVar, reconexão, retomada, idempotência, migração e rota.
- Painel na toolbar do MSFS continua como próxima etapa documentada; não incluído neste patch.

## 0.1.1-alpha — 2026-11-02

- Demo e comunicação SimConnect confirmadas em Windows real pelo piloto.
- Busca local restrita de `common.db` e `std.bin` para versões/instalações diferentes do NeoFly.
- Seletor permite `.bin` e `.db`; ferramenta informa formatos não SQLite sem tentar leitura não autorizada.
- Documentação atualizada e mais testes automatizados.
- Dados de NeoFly **não** foram localizados nem importados nesta versão.

## 0.1.0-alpha — 2026-11-02

- Início de projeto **independente** NeoFly, nome provisório AeroCarreira Lab.
- Implementado motor de telemetria, voo, contrato e saldo.
- Implementado painel desktop no Windows com demo sintética e conexão opcional SimConnect.
- Persistência de voo/saldo em SQLite.
- Inspetor seguro do banco `common.db` que copia antes de ler, preservando fonte e não exportando registros.
- Testes de lógica, banco e análise.
- **Pendente:** validação com simulador real e análise do banco real do usuário.
