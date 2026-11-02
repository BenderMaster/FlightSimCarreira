# Arquitetura: painel dentro do MSFS 2020

> **Requisito prioritário confirmado pelo piloto em 02/11/2026:** operar a carreira **sem Alt+Tab**. Consultar mapa, navegar pelas missões, aceitar contratos, ver pagamentos, frota e diário de bordo dentro do próprio simulador.

## Decisão técnica

- **Não migrar a lógica para dentro do processo do simulador.** Preservar um processo Windows externo, sem janela obrigatória, conectando ao MSFS 2020 por **SimConnect**.
- Empacotar um **painel HTML/CSS/JavaScript** próprio, integrado à toolbar do MSFS 2020 e distribuído como package para a pasta **Community**, construído com o SDK.
- O painel conversa com um servidor local mantido pelo motor de carreira (API HTTP e/ou WebSocket em `127.0.0.1`). **A compatibilidade da conexão entre UI in-game e serviço local depende de teste físico**.
- O motor concentra contratos, finanças, avaliador de voo, estado da carreira e persistência em **SQLite próprio**.
- A UI Windows atual é uma interface temporária/de diagnóstico; **não** deve tornar-se o fluxo principal de gameplay.
- No futuro, launcher simples ou serviço iniciado com o jogo para impedir Alt+Tab também na inicialização; não presumir que a pasta Community executa programas Windows automaticamente.

### Diagrama

```text
MSFS 2020 <--> SimConnect <--> FlightSimCarreira (processo Windows)
                                       |
                                  SQLite próprio
                                       |
                           servidor HTTP/WS local (127.0.0.1)
                                       |
                            Painel in-game (toolbar)
                             mapa/contratos/frota/avisos
```

## Fluxo de interface esperado

1. Abrir o MSFS; FlightSimCarreira disponibiliza seu serviço local.
2. Acionar o ícone **FlightSimCarreira** na barra superior do simulador.
3. Visualizar mapa da posição atual e rota da missão, com opções de zoom, recentralização e detalhes de aeroportos.
4. Aceitar/cancelar contratos elegíveis, planejar rota, examinar carga/passageiros, frota e combustível sem sair do voo.
5. Receber avisos discretos de missão, arremetida, pouso, pagamento e conclusão.
6. Consultar diário de bordo e progresso na mesma janela.
7. Se a ponte cair, mostrar desconectado e permitir reconexão, sem travar o simulador nem pagar missão em duplicidade.

## Confiabilidade e segurança

- SimConnect e regras de domínio **testáveis sem MSFS**, com telemetria simulada.
- Protocolo local versionado. Servidor associado apenas à interface de loopback, com autenticação da sessão para operações que alterem o saldo, contratos ou carreira.
- Não abrir porta para a LAN; validar mensagens e bloquear origens externas.
- Pacote Community **não deve sobrescrever arquivos globais de toolbar** nem modificar outros addons.
- Mapa deve usar fonte legalmente licenciada, com atribuições e modo offline quando viável; sem assumir que mapas de terceiros permitem incorporação.
- Nenhum arquivo de dados pessoais, banco real do NeoFly ou token/API key no repositório público.
- Usar logs com informações sensíveis removidas.

## Etapas de entrega (sem quebrar a v0.1.1)

1. **Motor estável:** completar voo real, detecção de decolagem/pouso e contratos; corrigir falhas de telemetria.
2. **Ponte local:** APIs para estado de voo, contratos, mapa e notificações, com testes automatizados e sem nova interface ainda.
3. **Painel mínimo:** provar que ícone aparece na toolbar, lê estado atual e executa um comando seguro (ex.: alternar página) no MSFS 2020.
4. **Painel jogável:** contratos, mapa com rota, progresso e diário de bordo.
5. **Instalação/usabilidade:** package Community + inicialização automática confiável do companion, sem Alt+Tab em uso normal.

## Critérios de aceitação

- Abrir/fechar painel durante voo sem travamentos ou perda de conexão.
- Aceitar contrato, seguir mapa e concluir voo **inteiramente dentro do MSFS**.
- Recuperar conexão após fechar/reabrir o painel.
- Nunca duplicar recompensa nem histórico ao reconectar.
- Testes locais e CI preservados; compatibilidade validada no MSFS 2020 Steam real.

## Referências técnicas

- [SimConnect SDK oficial MSFS 2020](https://docs.flightsimulator.com/html/Programming_Tools/SimConnect/SimConnect_SDK.htm)
- [Exemplo de panel toolbar](https://github.com/bymaximus/msfs2020-toolbar-window-template)
- [Exemplo de painel local web](https://github.com/MariusMyburg/msfs-panel-simaware)

**Status:** arquitetura aprovada como direção do projeto, ainda sem package Community implementado.