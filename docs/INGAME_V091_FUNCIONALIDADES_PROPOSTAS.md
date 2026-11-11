# FlightSim InGame — escopo proposto para v0.9.1 e próximas etapas

> Proposta de evolução após o teste físico do piloto em 10/11/2026
> (MSFS 2020 Steam): painel movível, altura correta, quatro telas responsivas,
> SimConnect e dados de carreira visíveis. Não é homologação automática
> das operações; o protótipo atual é somente leitura.
> A main v0.8.7 permanece intacta.

## Objetivo de produto

Durante um voo, o piloto deve conseguir operar a carreira pelo painel da
toolbar do MSFS, sem Alt+Tab. O aplicativo FlightSim Windows continua sendo o
motor Python/SQLite/SimConnect e deve funcionar em segundo plano, sem CMD
separado. A pasta Community não executa programas Windows automaticamente.

## Navegação — Midnight Tablet

- **Painel:** aeronave/telemetria, contrato ativo, fase do voo, avisos
  relevantes e ações rápidas contextualizadas.
- **Mercado:** abas Regional, Freelancer e Companhias (quando aplicável);
  ofertas determinadas pela sessão MSFS e habilitações reais do piloto;
  visualizar requisitos, aceitar/cancelar com confirmação.
- **Mapa / Planejamento / Despacho:** posição e proa reais, rota da missão,
  zoom e recentralização, waypoints, altitude, estimativas, peso/carga, combustível,
  checklist, exportação de .PLN e envio do plano/carga quando permitido pelo motor.
  Não prometer mapa VFR oficial; manter atribuição da base cartográfica.
- **Aeronave / Frota:** instrumento de combustível e desgaste, foto da aeronave,
  frota própria, seleção segura, abastecimento e manutenção somente em solo,
  sem alterações financeiras até receber confirmação do motor.
- **Carreira / Companhias:** piloto ativo, patente, XP, licenças por tipo,
  metas e salário semanal, candidatura e operações profissionais.
- **Finanças / Registro:** saldo, extrato, despesas e seguro, diário de voo,
  medalhas e relatórios, com operações financeiras sensíveis protegidas.

Em telas estreitas, organizar subabas e esconder comandos secundários sob
um menu; nunca reduzir os textos para tamanhos ilegíveis.

## Arquitetura obrigatória para escrita (nova ponte)

1. Manter read API v2 funcionando sem regressão.
2. Introduzir API de comandos versionada e distinta da leitura, vinculada
   a 127.0.0.1, com chave efêmera por sessão, validação de Origin/Host,
   método POST e esquema fechado por tipo de comando; negar CORS externo.
3. Receber apenas intenções de usuário e dados mínimos; nunca confiar em
   preço, salário, saldo, XP, altitude ou presença no aeroporto fornecidos
   pelo JavaScript. O motor revalida tudo com telemetria atual.
4. Enfileirar ações para a thread proprietária de Tk/SQLite/SimConnect.
   Não abrir segunda conexão de escrita SQLite ou segundo motor de voo.
5. Cada alteração financeira/contratual tem request_id único,
   transação idempotente e estado de retorno pendente/aprovado/recusado.
   A UI não mostra sucesso antes da confirmação efetiva do motor.
6. Guardas de solo/voo, conexão ativa, aeronave selecionada, licença,
   aeroporto confirmado pelo MSFS, payload/MTOW e contrato ativo continuam
   no backend, nunca apenas no HTML.
7. Desconexão e reconexão devem preservar a sessão sem duplicar contratos,
   pagamentos, abastecimentos ou conquistas. Redigir logs sem chaves.

## Incrementos sugeridos

### v0.9.0 Alpha.4 — base homologada parcialmente
- Ícone, iframe e telemetria funcionando no MSFS 2020.
- Janela movível e conteúdo responsivo: piloto confirmou no teste físico.
- Ampliar tipografia e substituir seta não renderizada pelo glifo vetorial.
- Novas operações continuam bloqueadas até existir autenticação de escrita.

### v0.9.1 — primeiro painel jogável
- Comandos autenticados com estado de confirmação e testes de rejeição.
- Mercado Regional / Freelancer, detalhes, aceite e cancelamento.
- Missão ativa e despacho já validado pelo motor, com confirmação.
- Sem alteração direta do simulador por JavaScript; SimConnect no companion.

### v0.9.2 — planejamento e mapa
- Mapa responsivo real com atribuição, posição/proa e rota por trecho.
- Waypoints, altitude, estimativa, checklist, combustível e carga.
- Salvar/abrir, exportar e enviar plano PLN pelo caminho já implementado.

### v0.9.3 — aeronaves e serviços
- Frota, aeronave ativa, inventário de combustível, desgaste.
- Abastecimento em solo, devolução permitida e manutenção,
  preservando custo, MTOW, idempotência e confirmação SimConnect.
- Mercado de aeronaves somente com validações físicas e financeiras.

### v0.9.4 — carreira e escritório
- Pilotos/perfis (troca apenas em solo), níveis/licenças/conquistas,
  companhias e metas, finanças, logbook e relatórios.
- Formulários complexos em subabas sem lotar o espaço do painel.

### v0.9.5 — fluxo sem Alt+Tab
- Inicializador único do FlightSim + MSFS Steam, ou companion na bandeja
  com inicialização configurável pelo usuário.
- Reconexão, diagnósticos acessíveis InGame e fechamento limpo.
- Sem browser externo, sem CMD adicional, sem instalação automática
  presumida pelo pacote Community.

## Critérios de aceitação a cada incremento

- Windows GUI/SimConnect e a v0.8.7 continuam íntegros; main sem merge
  antes da homologação no MSFS real.
- Testes Python 3.11/3.13 Windows/Linux, Playwright em janelas amplas/
  estreitas e build PyInstaller com smoke do WinForms.
- Nenhuma cobrança repetida, nenhuma missão paga por telemetria não verificada,
  nenhuma operação em voo que exija solo.
- UI legível e responsiva, sem área cinza ou perda do arraste da janela.
- Alt+Tab não é exigido nas operações implementadas; recursos ainda não
  migrados ficam marcados como pendentes, não como já funcionais.
