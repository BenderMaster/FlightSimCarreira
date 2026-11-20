# FlightSim v0.9.3 InGame Alpha.5 — compatibilidade dos IDs FacilityData

## Sintoma corrigido

Na Alpha.4, a consulta FacilityData chegou à fase de recebimento, mas o log mostrava:

`Tamanho inválido da resposta de instalação.`

A validação rejeitava uma mensagem de 16 bytes como se fosse um pacote de dados de instalação.

## Causa

Os IDs de recebimento do SimConnect são enumerações sequenciais. No cabeçalho do MSFS 2020, `SIMCONNECT_RECV_ID_PICK` pode ser inserido antes de `EVENT_EX1` quando `ENABLE_SIMCONNECT_EXPERIMENTAL` está definido. Essa opção desloca os IDs seguintes em uma posição.

Assim, os dois layouts possíveis são:

| Mensagem | Sem PICK experimental | Com PICK experimental |
|---|---:|---:|
| `FACILITY_DATA` | 28 | 29 |
| `FACILITY_DATA_END` | 29 | 30 |

O código anterior fixava apenas 29/30. No layout sem PICK, o ID 29 é o pacote de encerramento (16 bytes), mas era interpretado como um pacote FacilityData, cujo cabeçalho + primeiro DWORD de dados exige ao menos 44 bytes. Isso produzia a mensagem observada.

Referências:
- [Cabeçalho SimConnect.h com PICK condicional](https://github.com/mars-f/msfs-weather-balloon/blob/main/SimConnect.h)
- [Documentação Microsoft — SIMCONNECT_RECV_ID](https://docs.flightsimulator.com/html/Programming_Tools/SimConnect/API_Reference/Structures_And_Enumerations/SIMCONNECT_RECV_ID.htm)
- [Documentação Microsoft — SIMCONNECT_RECV_FACILITY_DATA](https://docs.flightsimulator.com/html/Programming_Tools/SimConnect/API_Reference/Structures_And_Enumerations/SIMCONNECT_RECV_FACILITY_DATA.htm)

## Correção

- Reconhece DATA IDs 28/29 e END IDs 29/30.
- Diferencia DATA e END pelo tamanho nativo do pacote (mínimo 44 bytes para DATA; 16 bytes para END).
- Confirma que o Request ID corresponde a uma consulta ainda pendente antes de processar a resposta.
- Valida `IsListItem` como DWORD completo, conforme o cabeçalho C do SDK.
- Mensagens inesperadas geram diagnóstico com `dwID`, `dwSize` e `cbData`, em vez de uma mensagem genérica.
- Mantém a política conservadora: ausência de dado continua como “Não verificado”.

## Validação

A CI adiciona testes para os dois layouts de IDs, incluindo o caso crítico `dwID=29` com 16 bytes (END) e `dwID=28` com dados (DATA).

Os testes automatizados não substituem a homologação no MSFS 2020 Steam. A correção só deve ser considerada homologada depois de consultar aeroportos reais no simulador.
