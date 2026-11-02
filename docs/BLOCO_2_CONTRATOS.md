# Bloco 2 — Mercado regional e contratos freelancer

## Princípios

- Construir propostas **na região atual**; o piloto escolhe a partir da posição SimConnect perto de um aeroporto ou da base no perfil enquanto offline.
- O catálogo mundial `airportsdata` (licença MIT) é **referência de coordenadas**, não prova de que cada aeródromo aparece no MSFS; fallback nativo apenas SBRF, SIPE, SIFC e SBJP.
- Máximo de **13 ofertas** em SQLite para **um aeroporto de origem** por vez, sem gerar missões em outros continentes. Candidatos globais são carregados como catálogo de aeroportos pela biblioteca (alguns MB na RAM, não contratos).
- Diário e saldo ficam no banco SQLite original do FlightSimCarreira; o NeoFly não é editado nem utilizado para gerar ofertas.
- Propostas de uma região renovadas no próximo dia UTC (ou ao trocar origem), não geradas ad infinitum ao clicar Atualizar.
- Um mesmo ID de contrato regional/freelance é pago **somente uma vez**, além da proteção já existente por identidade de voo. Em novo voo com ID de contrato antigo, voo pode ser registrado mas não gera nova recompensa.

## Níveis de acesso (inicial, ajustável)

| Categoria | Nível | Habilitações | Horas mínimas |
|---|---:|---|---:|
| Carga | 1 | PPA | 0 |
| Turismo | 2 | PPA | 0,25 |
| Passageiros | 2 | PPA | 0,25 |
| Táxi aéreo | 3 | PCA | 0,7 |
| Humanitário | 4 | PCA | 1 |
| Médico | 6 | PCA | 2 |
| Executivo | 8 | PCA + IFR | 3 |
| Busca e resgate | 10 | PCA + IFR | 5 |
| Operação especial | 12 | PLA | 8 |

Nível = função de XP do diário de bordo, começando em 1. Para alcançar nível N+1, XP total deve ser ao menos `100*N+15*N*N`; referências balanceáveis. Voos anteriores continuam nas estatísticas, sem XP retroativo.

## Freelancer

- Piloto seleciona uma proposta **sem utilizar aeronave do inventário próprio** no modelo econômico do addon. Seu pagamento é salário por serviço, sem custo de compra/locação.
- A proposta mostra a aeronave do contratante. Até a integração com inventário/alteração de aeronave no MSFS, usuário precisa selecionar manualmente esse modelo no simulador.
- Modelos previstos: Cessna 152 (nível 1), C172 (nível 2), Baron G58 (6), King Air 350i (8), Citation CJ4 (11). Modelos avançados exigem habilitação, horas, experiência por família e pelo menos um voo registrado naquele modelo.
- Leitura `TITLE` no SimConnect é experimental. Pagamento freelance é liberado **somente** após confirmar o modelo da aeronave na decolagem e no pouso. Se não funcionar no MSFS real, diagnosticar sem inventar crédito nem forçar o usuário a perder progresso.
- O addon **ainda não aluga/carrega aviões automaticamente**, não verifica matrícula contra frota própria e não altera o simulador.

## Próximas atividades

- Enriquecer tipos de missão com passageiros, carga física, temporizadores, embarque, busca e localização real, pousos alternativos e avaliação específica.
- Permitir desbloqueio de novas aeronaves com licenças, experiência e regras claras da frota.
- Implementar as opções separadas `Exigir provas` (desligado por padrão) e `Falhas simuladas` (desligado por padrão); provas opcionais não revogam habilitações anteriores.
- Migrar o mercado para o painel de toolbar integrado ao MSFS sem Alt+Tab, com API local e testes de reconexão.
- Não distribuir `airportsdata`/base de aeroportos sem cumprir a licença MIT do fornecedor; instalação atual vem diretamente do PyPI.

## Estado da entrega

`v0.3.0-alpha.1`: regras, persistência, UI e testes implementados. O MSFS real, leitura do modelo e catálogo mundial ainda precisam de validação física. As operações avançadas de missão usam nesta etapa as mesmas regras básicas de conclusão por aeroporto.
