# FlightSimCarreira — escopo funcional aprovado

Decisões levantadas na conversa em 02/11/2026. **Planejamento:** não confundir requisitos com recursos já implementados.

## Sistemas desejados

1. **Piloto:** criação, base, indicativo, experiência, reputação, habilitações e progressão.
2. **Carreiras:** autônomo, contratado e dono de empresa.
3. **Contratos:** carga, passageiros, turismo, táxi aéreo, resgate, emergência e operações especiais.
4. **Mercado:** missões geradas com demanda, disponibilidade, prazos e remuneração dinâmica.
5. **Finanças:** pagamentos, taxas, despesas, impostos opcionais e empréstimos.
6. **Frota:** compra, aluguel, revenda, cadastro e localização dos aviões.
7. **Manutenção:** combustível, inspeções, avarias, seguro e acidentes.
8. **Despacho/planejamento:** meteorologia, peso e balanceamento, pistas, iluminação, rota, combustível e mapa.
9. **Avaliação operacional:** segurança, procedimentos, arremetidas, voos noturnos e incidentes.
10. **Passageiros/cargas:** peso, conforto, satisfação e limites físicos.
11. **Eventos:** ocorrências e alterações durante a missão.
12. **Diário de bordo:** voos, XP, estatísticas, conquistas e histórico.
13. **Companhia própria:** marcas, bases, contratos, expansão e linhas.
14. **Equipe:** pilotos e gestores IA com operação delegada.
15. **Gestão empresarial:** rotas recorrentes, concorrência e expansão.
16. **Interface dentro do MSFS 2020:** toolbar com mapa, contratos, frota e informações sem Alt+Tab.

## Preferências específicas do piloto

- **Falhas provocadas pelo addon: ativar/desativar nas configurações.** Não confundir com a opção de falhas própria do MSFS: o addon não pode controlar/configurar globalmente o simulador sem confirmação e documentação técnica.
- **Mapa:** prioridade a explorar dados do próprio MSFS, incluindo pista, tráfego e referências já disponíveis, sem assumir que o mapa VFR nativo oferece API de incorporação.
- **Jogadores online:** desejável visualizar aeronaves de outros participantes quando o modo online estiver ativo. **Limitante conhecido:** SimConnect RequestDataOnSimObjectType pode retornar tráfego IA, mas não necessariamente jogadores multiplayer do MSFS 2020. Exige prova de conceito/integração adicional; fallback não deve inventar posições de jogadores.
- **Companhias aéreas reais:** permitir referência a empresas e indicativos, integrando configurações de companhia, aeronave e modelo. Marcas/logos de terceiros têm licenças próprias.
- **Skins/liveries:** indexar pinturas instaladas localmente, model matching por aeronave e companhia; não copiar ou redistribuir pinturas protegidas sem permissão. Os demais jogadores podem ver modelos/liveries genéricos conforme as configurações do simulador.
- **Desenvolver por blocos:** cada bloco com domínio, persistência, interface, testes, versionamento e migração segura. O programa externo é provisório, projetado para posterior painel na toolbar.

## Bloco 1 — Perfil e habilitações (v0.2.0-alpha.1)

**Entregue para teste no Windows:**
- Cadastro de **um piloto por carreira local**: nome, indicativo e base ICAO, editáveis.
- O painel **Meu piloto / Habilitações** exibe voos, horas, XP e habilitações virtuais.
- Migração SQLite **aditiva**: saldo, voos e checkpoint permanecem. Voos antigos entram na contagem de voos/horas, mas não recebem XP retroativo inventado.
- XP **após criar piloto**: 25 por voo finalizado + 15 por missão paga; ganho atômico na mesma transação do pouso, uma única vez, sem bônus por pousos excessivamente suaves.
- Habilitação virtual inicial **PPA**, seguida de **PCA**, **IFR**, **MLTE**, **PLA**, com limites provisórios de voos, XP e pré-requisitos. Os títulos são apenas progressão do jogo, **não credenciais aeronáuticas reais**.
- Ação **Concluir etapa** só é habilitada quando todos os pré-requisitos são satisfeitos. Status permanece salvo entre reinicializações.
- **Nenhuma restrição nova nos contratos antigos**; habilitações avançadas ainda não liberam rotas ou aviões nessa entrega. Faz parte de um bloco posterior, após refinarmos as regras.

| Código virtual | Mín. voos | Mín. XP | Pré-requisito |
| --- | ---: | ---: | --- |
| PPA | 0 | 0 | inicial no cadastro |
| PCA | 4 | 160 | PPA |
| IFR | 8 | 320 | PPA |
| MLTE | 10 | 450 | PCA |
| PLA | 25 | 1.500 | PCA + IFR + MLTE |

**Importante:** esses limites são apenas defaults provisórios para teste. Não refletem cargas horárias e requisitos regulatórios reais; exigências de avaliação prática, cursos e aeronaves serão discutidas antes de restringir a progressão.

## Próximos blocos possíveis

- **Bloco 2:** catálogo de aeronaves, requisitos por categoria, contratos desbloqueáveis, perfis e testes de habilitação.
- **Bloco 3:** geração de contratos, passageiros, cargas e economia dinâmica.
- **Bloco 4:** gestão de frota, manutenção e configuração de falhas no addon.
- **Bloco transversal obrigatório:** painel dentro do MSFS e mapa; plano técnico em `ARQUITETURA_IN_GAME.md`.
