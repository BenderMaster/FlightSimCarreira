# FlightSimCarreira v0.7.7 Alpha.1 — Inventário, payload e despacho

## Escopo implementado
- Combustível é persistido em `fleet_fuel` por `aircraft_ref` dentro do `carreira.db`; reconectar o MSFS dias depois **não** simula consumo durante o tempo offline.
- Desgaste segue persistente por `legacy:<code>` ou `unit:<id>` e não é recalibrado a cada sessão.
- A Dashboard mostra alertas quando combustível ou integridade atinge <=20%; mensagens são do aplicativo, sem efeitos/mensagens 2D dentro do MSFS nesta alpha.
- Abastecimento via diálogo do WebView2 com valor TOTAL em litros, custo e devolução. A quantidade é distribuída proporcionalmente aos tanques reconhecidos; transação de saldo e atualização do inventário são atômicas e em seguida o worker tenta reconciliar com o MSFS.
- Reembolso só ocorre para litros comprovadamente comprados no novo inventário `refundable_fuel_v077`. Litros iniciais calibrados são gratuitos e não geram ressarcimento. Litros comprados e consumidos deixam de gerar ressarcimento. Os abastecimentos de versões anteriores não são automaticamente classificados como retornáveis sem histórico inequívoco por tanque.
- Gerador diário de missões usa manifesto ficcional e peso determinísticos por ID. O JSON da oferta e o checkpoint da missão retêm descrição e `payload_kg`.
- O clique em **Aceitar missão** exporta `.PLN` e solicita carregamento no SimConnect, sem confirmação extra, somente se houver conexão e aeronave parada e compatível. Clique em **Preparar Voo / Despacho** tenta novamente.
- Carga: `PAYLOAD STATION WEIGHT:n` exige estação indexada 2..15 que esteja vazia, não ocupa piloto ou passageiro existente; só escreve com `SIM ON GROUND`, GS<=2 kt, modelo correto, `TOTAL WEIGHT` e `MAX GROSS WEIGHT` disponíveis e margem >=1 lb.
- O status de carga só é **confirmado** após amostra subsequente mostrar o peso esperado na estação. Payload pendente mantém checkpoint; nunca afirmar que o MSFS aceitou um ajuste pela simples solicitação.
- Bônus de peso +2,5% sobre pagamento e XP na conclusão do contrato, quando o peso do MSFS é válido, <=MTOW e a carga da missão foi comprovadamente aplicada. Mantém a fórmula anterior de multiplicador do despacho e as proteções contra créditos duplicados.
- METAR destino prioritário NOAA; dados do MSFS aparecem somente como fallback se NOAA ausente, ou quando a opção futura `show_msfs_metar_alongside_noaa` for habilitada.

## Limitações explicitamente pendentes
- **Coordenadas de aeroportos ainda não provêm diretamente da lista de facilities do MSFS**. O SDK fornece `SimConnect_RequestFacilitiesList`, mas o adaptador Python utilizado não expõe integração completa e validada neste projeto. Não devemos substituir mapas por coordenadas arbitrárias ou declarar precisão 1:1. A implementação do leitor de facilities para origem/destino, cache por instalação/cenário e prova de correspondência ICAO será etapa de homologação separada.
- O SDK indica que `SimConnect_FlightPlanLoad` retorna sucesso de requisição, mas não confirma que o GPS/Mapa VFR da aeronave atualizou exatamente; verificar no MSFS real. O carregamento de peso também exige validação da resposta de cada aeronave; aviões com estações proprietárias podem não aplicar.
- Não ajustar peso do piloto/ocupantes existentes; uma aeronave com todas as estações ocupadas ficará com carga pendente.
- O ícone oficial da aplicação permanece inalterado até aprovação do novo ícone. O botão de despacho usa uma silhueta de decolagem inspirada no exemplo enviado.
- Não há injeção de mensagens 2D no MSFS nem falhas mecânicas simuladas nesta versão.

## Testes manuais no MSFS 2020
1. Backup com o app fechado: `%APPDATA%\AeroCarreira-Lab\carreira.db`. Reabrir com o mesmo piloto e cada aeronave; verificar litros e desgaste.
2. Reiniciar MSFS com combustível arbitrário diferente; confirmar que addon solicita restauração do inventário salvo, sem compras adicionais.
3. Abastecer de 30 para 60 L; conferir o débito apenas uma vez e os dois tanques. Devolver para 45 L; conferir ressarcimento proporcional. Confirmar que combustível não comprado não gera dinheiro.
4. Aceitar missão do C152 em solo parado com assento de passageiro vazio; confirmar peso em payload station e <= MTOW antes de decolar.
5. Aceitar com estação ocupada ou peso acima do limite; não escrever payload, informar pendência.
6. Conferir bônus de peso e readback no MSFS após voo concluído; não permitir bônus se payload não confirmado.
7. Comparar origem/destino de aeroportos customizados com a base de facilities do MSFS; registrar discrepâncias para próximo patch específico.
