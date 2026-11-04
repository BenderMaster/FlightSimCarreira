# v0.7.8 — roteiro de homologação

1. Reinicie o MSFS 2020 com C152 em solo e execute o app. Confirmar no log `AEROPORTOS MSFS: N aeródromos confirmados`, onde N deve ser não zero. Antes disso, mercado deve permanecer vazio.
2. Mercado regional em SNRU: somente aeródromos retornados pela sessão MSFS e destinos realmente instalados. `SNBJ` não aparece se o MSFS não o lista. Não há fallback externo em problemas de SimConnect. Reiniciar o MSFS obriga nova consulta.
3. Aeroporto de contrato pré-existente ausente: contrato preservado no save, mas destino marcado não verificado, sem exportação, sem aceitar novo contrato até completar o antigo.
4. Abrir Abastecer: popup pode definir litros. Confirmar envia número JSON ao servidor local (202), não mais HTTP 400. Conferir caixa no addon, combustível real no MSFS e eventual reversão por falha. Testar somente em solo, com inventário calibrado.
5. Aceitar contrato novo: envia `.PLN` ao SimConnect quando origem/destino confirmados, sem confirmação secundária. O comando de `FlightPlanLoad` **não equivale a rota carregada no GPS ou no mapa VFR**: o ATC poderá estar atualizado enquanto a aeronave requer importação específica do plano. É limitação da API externa pública MSFS 2020, não sucesso completo.
6. Carga: deve permanecer `verified` após confirmação pelo SimConnect, sem regressão de peso.
7. Ícone Windows: verificar Explorer e barra de tarefas.
8. Backup anterior no `%APPDATA%\AeroCarreira-Lab\carreira.db`. Não tocar nem migrar destrutivamente o save.

Se o catálogo não aparecer, reportar `airport_catalog_error` e versão da instalação MSFS; evitar ofertar coordenadas externas só para popular a UI.

**CI verde não substitui o MSFS real.**