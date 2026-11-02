# Reconhecimento do esquema NeoFly 4 — 02/11/2026

## Material analisado

Arquivo recebido do piloto: `neofly_schema_report.json` (gerado pelo analisador do FlightSimCarreira).

O relatório informa:
- `kind: neofly-schema-report`
- `format: SQLite`
- `size_bytes: 991232` (**tamanho do arquivo de origem examinado**, não do relatório).
- `read_only: true`, `source_modified: false`, `contains_personal_records: false`.
- **54 tabelas** com nomes, tipos SQL e marcadores de chave primária.
- **Não contém registros**, portanto **não** permite conhecer saldo real, aeronaves possuídas, nome do piloto, número de voos, valores de XP, id do perfil ou relações concretas entre dados.

A análise foi de **estrutura** de banco. Não inventar valores nem concluir semântica exata de campos com base apenas no nome.

## Candidatos à importação futura

| Destino FlightSimCarreira | Tabela NeoFly | Campos observados | Observação |
|---|---|---|---|
| Perfil | `players` | `id`, `name`, `pilotCurrentICAO`, `totalFlyTime`, `xp`, `cash`, `rank`, `reputation`, `currentPlane` | Conferir unidades, enums e perfil ativo |
| Piloto ativo | `currentpilot` | `pilotID` | Identificação precisa ser validada por exemplos locais |
| Diário de voo | `flightlog` | `id`, `date`, `departure`, `arrival`, `dist`, `flytime`, `ownerId`, `planeId`, `landingfpm`, `crash` | Reconciliação de IDs e unidades |
| Histórico de contratos | `joblog` | `id`, `departure`, `arrival`, `reward`, `xp`, `status`, `ownerId`, `planeId` | Tipos e códigos status desconhecidos |
| Finanças | `finances` | `id`, `date`, `description`, `incomes`, `expenses`, `balance`, `ownerId` | Evitar duplicar movimentos ou saldo |
| Aeronaves em hangar | `hangar` | `id`, `liveryId`, `Location`, `statusEngine`, `statusHull`, `airframe`, `currentFuel`, `ownerId`, `tailNumber` | Relacionar aeronaves e libré ao catálogo |
| Modelos de aeronave | `aircrafts` | `id`, `name`, `type`, `cruiseSpeedktas`, `fuelCaplbs`, `maxPayloadlbs`, `maxTakeOfflbs`, `Pax` | Referências de especificação, não dados proprietários a redistribuir |
| Aeródromos | `airport` | `icao`, `name`, `laty`, `lonx` | Não redistribuir catálogo do NeoFly; usar dados licenciados próprios |

## Cuidados obrigatórios

- A importação deve acontecer **no computador do usuário**, usando uma **cópia** ou SQLite aberto em **modo somente leitura**. Nada de editar o original NeoFly.
- Antes da importação definitiva: **prévia**, validação dos relacionamentos, resumo dos dados, backup da carreira própria e confirmação expressa.
- IDs e chave de origem devem garantir **idempotência**: importar novamente não pode criar voos, aeronaves ou pagamentos duplicados.
- Não copiar/escrever tabelas fora do escopo (ex. `api`, `settings`), sobretudo potenciais tokens/chaves; jamais enviar banco ou dados pessoais ao GitHub público.
- Separar a lógica de importação de leitura do NeoFly do motor de carreira independente; não depender do NeoFly para executar o jogo.
- Suportar variações entre versões e recusar formato/colunas desconhecidos com mensagem segura, sem adivinhar.
- A importação de catálogo, imagens e recursos do NeoFly não está autorizada por este relatório: respeitar licenças e criar dados próprios.

## Próximo marco técnico

1. Criar **import preview** local e somente leitura para `players`, `currentpilot`, `flightlog`, `hangar` e `finances` (sem alterações).
2. Validar códigos de status, datas/épocas e unidades usando exemplos locais minimizados, sem publicá-los.
3. Testar múltiplos perfis, banco vazio, banco parcialmente migrado, tipos inesperados e duplicidade.
4. Importação efetiva só depois de confirmação do usuário, com backup da nossa carreira.

**Status:** esquema compatível com SQLite confirmado; **importação ainda não implementada nem validada**.