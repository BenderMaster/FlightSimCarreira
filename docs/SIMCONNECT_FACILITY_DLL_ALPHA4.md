# FlightSim v0.9.3 Alpha.4 — correção da DLL FacilityData

## Diagnóstico

A captura mostra `SimConnect_AddToFacilityDefinition not found`. Essa função e `SimConnect_RequestFacilityData` fazem parte da API FacilityData do SimConnect para MSFS 2020, disponível desde a versão 0.19.0. A listagem de aeroportos pode funcionar mesmo quando essas funções não estão presentes, porque `SimConnect_RequestFacilitiesList` é uma API antiga.

O pacote Python-SimConnect carrega por padrão uma DLL própria ao lado de `SimConnect.py`. Se essa DLL for anterior à API FacilityData, o inventário de aeroportos pode aparecer, mas as consultas individuais de ILS, VASI/PAPI, iluminação e posições de combustível falham.

## Correção

Antes de abrir a conexão, o FlightSim procura uma DLL cliente do SDK Core que exporte as duas funções necessárias. A mesma DLL é usada para abrir o handle e executar todas as chamadas; nunca se abre com uma versão e se chama a API por outra.

Ordem de procura:
1. `FLIGHTSIM_SIMCONNECT_DLL` — caminho completo da DLL.
2. `SIMCONNECT_DLL` — caminho completo alternativo.
3. `MSFS_SDK\SimConnect SDK\lib\SimConnect.dll`.
4. `MSFS2020_SDK\SimConnect SDK\lib\SimConnect.dll`.
5. Caminhos padrão `C:\MSFS SDK` e `C:\MSFS 2020 SDK`.

O resolvedor carrega cada candidato e valida os exports `SimConnect_AddToFacilityDefinition` e `SimConnect_RequestFacilityData`. Uma DLL sem qualquer um deles é rejeitada. Se nenhuma DLL compatível existir, a consulta é bloqueada com diagnóstico explícito e os dados permanecem “Não verificado”.

## Como preparar o computador

- Instale/atualize o **MSFS 2020 SDK Core** pelo simulador: Developer Mode → Help → SDK Installer (Core).
- Reinicie o FlightSim depois da instalação para herdar a variável de ambiente `MSFS_SDK`.
- Se o SDK estiver numa pasta não detectada automaticamente, defina `FLIGHTSIM_SIMCONNECT_DLL` com o caminho completo para `SimConnect.dll` do SDK.

## Limites de validação

A CI testa a seleção da DLL, a rejeição de binários sem os exports e a passagem do caminho selecionado ao construtor Python-SimConnect. Ela não substitui o teste físico no MSFS 2020 Steam, pois só o simulador real pode confirmar os pacotes FacilityData e os campos retornados por cada cenário/aeroporto.
