# Changelog

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

### Validação física no MSFS 2020 (02/11/2026)
- Confirmado pelo piloto: missão SIPE → SIFC concluída e encerrada na v0.1.2, com decolagem 19:45:14, pouso 19:55:07 e −172 ft/min estimados.
- Recompensa de $420 creditada uma vez no log visível; caixa mostrado $6.270; aplicativo exibiu "Nenhum contrato ativo".
- SimConnect aparecia conectado na captura após o pouso. Não foi comprovada ainda a retomada automática depois de uma queda real durante o voo, nem a ausência de duplicidade após reabrir o aplicativo.
- Evidência recebida no chat; não publicar captura de tela nem banco de carreira no repositório público.


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
