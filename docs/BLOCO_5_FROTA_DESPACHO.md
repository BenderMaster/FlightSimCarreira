# Bloco 5 — Frota individual, despacho e primeiro painel no jogo (v0.6.0 Alpha.1)

**Estado da implementação:** motor, GUI Windows, SQLite, ponte HTTP e painel navegador testados em ambiente de desenvolvimento; SDK de toolbar e troca de aeronave **não validados no MSFS Steam físico**. Não apresentar projeto-fonte como addon in-game já instalado.

## Frota individual e mercado

- Gestão **separada da frota legada** para preservar o C152 inicial e investimentos anteriores.
- **Novas:** uma instância individual por compra, registro próprio, estado inicial 100%, preço no catálogo de economia.
- **Segunda mão:** 5 ofertas determinísticas por aeroporto e semana, com preço reduzido, desgaste e horas de voo anteriores; cada oferta pode ser comprada uma única vez.
- **Aluguel:** períodos de 1–168 h, pagando antecipado, sem propriedade; expiração impede novas seleções. Não altera fisicamente a aeronave no MSFS.
- **Revenda:** somente aviões próprios novos/usados, calculada abaixo do custo pago; C152 inicial e alugados não podem ser vendidos.
- **Revisão e histórico:** serviço pago restaura a condição dos exemplares próprios avançados; registros preservados na tabela `fleet_log`.
- **Seleção/posição:** escolha de ativo na carreira; ao concluir um voo da aeronave própria, desgaste e aeródromo de destino são atualizados. Estoque legado pode continuar no fluxo antigo.
- **Economia e banco:** lançamentos financeiros atômicos e backups antes da migração em `carreira.pre_v060.backup.db`. Dados de carreira vivem somente no `%APPDATA%\AeroCarreira-Lab`, separados do NeoFly.

**Aeronaves instaladas no computador:** lê `UserCfg.opt` e os `aircraft.cfg` encontrados em Official e Community, inclusive títulos de variantes de pinturas e addons. Isso prova apenas **arquivos de instalação legíveis**, não licenças, elegibilidade de Marketplace, propriedade da aeronave no jogo, ou capacidade de selecioná-la via SDK. O catálogo comercial da carreira continua limitado às aeronaves suportadas pelo modelo econômico (C152/C172/G58/King Air/CJ4).

## Despacho por contrato

- **Offline:** aceita contrato a partir da base cadastrada mesmo antes de conectar o SimConnect; gera `.PLN` com partida/destino. Em solo/conectado, solicita carregamento via SimConnect. O arquivo também pode ser importado manualmente no MSFS.
- **Planejamento:** mostra distância, minutos estimados, reserva de combustível, altitude e checklist de clima, horário, assistência, pista/iluminação, rota, combustível e peso.
- Clima ao vivo, hora real, assistências, confirmação de pista e rota são **declarações do usuário**, não evidência operacional capturada pelo SDK. Vento, sim rate, peso e combustível têm leitura opcional via SimConnect, sujeita à disponibilidade do modelo.
- **Bônus de até +18%** aplicado ao **valor bruto e XP** de contratos elegíveis, somando fatores confirmados (clima +3%, horário +3%, assistências +3%, pista +2%, rota +2%, combustível +2,5%, peso +2,5%). Não há bônus retroativo e ele não usa a economia de solo para aumentar os minutos voados.
- Condições verificadas no momento da **decolagem**, com congelamento persistido no checkpoint; alterar o checklist depois não muda voo iniciado. O MSFS pode reportar nomes com prefixo do fabricante, tratados como equivalentes apenas quando o modelo base corresponde. Sim rate ≠ 1 desativa o componente de horário real.
- **Pouso:** crédito do contrato, bônus, XP, despesas e estado do voo são registrados atomicamente, sem duplicar após reinício/reconexão.
- Alguns itens são estimados; este sistema **não certifica** segurança de voo nem garante mapas aeronáuticos atualizados. Pistas sem luz devem ser conferidas no próprio simulador e em documentação apropriada.

## Integração com o MSFS 2020

| Recurso pedido | Estado nesta Alpha |
| --- | --- |
| Gerar rota .PLN antes de entrar no mundo | Implementado / teste local |
| Solicitar carregar .PLN pela sessão SimConnect em solo | Comando implementado; confirmação em voo físico ainda necessária |
| Inventariar aircraft.cfg do Official/Community | Implementado em modo somente leitura |
| Selecionar avião na frota virtual | Implementado; seleção no MSFS ainda manual |
| Configurar aeronave e montar voo automaticamente no Mapa-Múndi | **Não implementado:** API pública do MSFS 2020 não documenta esse fluxo completo |
| Trocar aeronave automaticamente após entrar no mundo | **Não implementado**: `FlightLoad` pode restaurar sessão e interromper voo; exige protótipo sob controle do piloto |
| Painel local no navegador (127.0.0.1:8769) | Implementado e testado (posição, contrato, caixa e esboço geométrico de rota) |
| Projeto-fonte do painel toolbar SDK | Presente em `in_game/toolbar/`, **não compilado nem testado no MSFS** |
| Mapa VFR nativo e jogadores online no painel | **Não implementado**: sem API confiável de incorporação validada |
| Meteo/pistas/iluminação obtidas automaticamente do jogo | Parcial: telemetria disponível + confirmação manual; sem base meteo/runway validada |

### Próximas provas técnicas no MSFS Steam

1. Em solo, gerar `.PLN` com missão aceita **antes** de iniciar voo, importar/solicitar carregamento; conferir visualmente no VFR/GPS e aeronave escolhida manualmente.
2. Escanear instalação local e confirmar C152 e livery addon, avaliando títulos reais do SimConnect; não enviar pastas de aeronaves ao repositório.
3. Realizar missão curta com checklist, verificar XP, bônus e dinheiro no diário/extrato; repetir teste com simulador reiniciado no meio para garantir idempotência.
4. Abrir painel local no browser. Só depois tentar compilar o SDK para Community em **instalação de teste**, sem sobrescrever toolbar original. Reportar erros de Coherent/iframe.
5. Só após sucesso da toolbar, planejar operações seguras de contratos in-game com autenticação e confirmação, e avaliar alternativa de templates `.FLT` para trocar aeronave antes de iniciar o voo.

**Fontes:**
- https://docs.flightsimulator.com/html/Programming_Tools/SimConnect/API_Reference/Flight_Plan/SimConnect_FlightPlanLoad.htm
- https://docs.flightsimulator.com/html/Programming_Tools/SimConnect/API_Reference/Flight_Plan/SimConnect_FlightLoad.htm
- https://docs.flightsimulator.com/html/Programming_Tools/SimConnect/SimConnect_SDK.htm
- Consulte também `docs/ARQUITETURA_IN_GAME.md` e `in_game/toolbar/README.md`.


## Validação de interface v0.6.0 pelo piloto (03/11/2026, screenshots)

**Confirmado pelo piloto no Windows real:**
- Tela **Frota 2.0** abre e lista pelo menos um exemplar legado Cessna 152, com conservação e aeródromo SBRF.
- **Mercado de segunda mão** apresenta ofertas de aeronaves com preço, horas e condição; piloto relatou que navegação/consulta funcionam.
- **Consulta às aeronaves instaladas no MSFS** foi reportada como funcional pelo piloto; não há ainda prova de cada variante/livery ou de direitos de licença.
- **Painel local** abre no navegador e mostra SimConnect ativo, saldo R$ 9.376, fase em solo, modelo Cessna 152, combustível, contrato SNPO → SNAE e traçado geométrico da rota.

**Ainda precisa de validação física:**
- Efetivar compra, aluguel, revenda, pagamento, manutenção e persistência dessas transações após reinício.
- Verificar se o aeródromo do exemplar legado SBRF é atualizado ao concluir missões em outros aeroportos; não inferir bug só pela tela da frota.
- Confirmar leitura de aeronaves adicionais instaladas e correspondência com o modelo escolhido na carreira.
- Não confundir painel no navegador com **toolbar dentro do MSFS**; última ainda é experimental.
- Validar bônus de realismo, despacho e pagamentos em missão real.

Evidência: capturas fornecidas pelo piloto na conversa. Não publicar screenshots pessoais, dados do perfil ou bancos locais no repositório público.

## Hotfix v0.6.1 — localização e combustível

- O Cessna starter persistia em SBRF mesmo após pouso confirmado perto de SNAE; antes somente fleet_units era atualizado.
- Correção para aeronaves starter, alugadas, novas e usadas, inclusive voos livres; freelancer/companhia não movimentam a frota particular.
- Recuperação única do último destino conhecido da aeronave starter, sem alterações de dinheiro, histórico ou XP.
- Inventário SQLite de combustível por tanque: calibração inicial em solo, consumo observado, correção limitada de reabastecimento pelo menu MSFS quando suportada e abastecimento pago.
- Se o modelo não oferece capacidades e tanques suficientes, o programa não força escrita no MSFS. Compatibilidade real segue pendente de validação.
- Desligar o controle gera penalidade de 30% em remuneração e XP, congelada na decolagem. Abastecimento pago não é cobrado duas vezes.
- 115 testes locais aprovados e testes gráficos da interface. Ver o roteiro de validação física no README.
