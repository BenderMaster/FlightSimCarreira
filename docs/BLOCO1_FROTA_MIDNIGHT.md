# Bloco 1 — Frota/Hangar

## Arquitetura de apresentação
O menu lateral continua sempre fixo. Frota é uma página `#fleet-page`, não um popup ou `#module-page` com ações clássicas. Estrutura: lista rolável à esquerda, imagem/indicadores do exemplar no centro, ações à direita. Desktop reduzido vira duas colunas e, no menor tamanho, pilha rolável.

## Fonte de verdade
`FleetManager.all()` mistura três domínios. A página filtra rigorosamente `legacy:` e `unit:` (proprietários), exclui `rent:` (aluguel) e `contract:` (freelancer). Selecionar um cartão da lista muda apenas o foco visual; mudar `active_aircraft_ref` exige clicar explicitamente "Definir como ativa" em solo, com validação de propriedade no backend.

## Foto e banco
`fleet_photos(aircraft_ref PRIMARY KEY, jpeg BLOB, updated_ns INTEGER)`, criada aditivamente por `Storage`. Foto original lida por diálogo Tk iniciado por comando autorizado. Pillow transposta orientação EXIF, reduz sem deformar, converte para RGB, compacta JPEG e valida tamanho. Quadro HTML usa `object-fit:contain`. A imagem é acessada na WebView somente via `/fleet-photo/<HMAC_SHA256_do_ref>.jpg?v=<updated_ns>`; conteúdo é servido de memória local com chave aleatória da sessão, nunca de diretórios do computador. A Dashboard recebe a mesma URL do exemplar ativo. Foto removida retorna ao padrão. C152 tem a foto padrão já licenciada; modelos sem foto exibem placeholder genérico.

## Operações
- **Selecionar:** só aeronave própria, proibido em voo.
- **Abastecer:** reaproveita o diálogo de litros somente no avião ativo, conectado em solo, respeitando limite de peso e caixa; não cobra automaticamente por apenas abrir página.
- **Revisar:** confirmação humana, chama `Storage.service_aircraft` para legado e `FleetManager.service` para exemplares adquiridos, preservando transações do ledger.
- **Foto:** upload/remoção independentes por ref.
- Compra/aluguel não aparecem na página Frota; função antiga fica disponível até a futura área Mercado de Aeronaves.

## Testes
- Unidade: somente próprios na coleção, exemplos de mesmo modelo não compartilham foto, persistência após reabrir SQLite, bytes JPEG válidos, foto de retrato preserva proporção, aluguel recusado, rota loopback protegida, foto da Dashboard idêntica à da Frota.
- Playwright: menu lateral, cards, cabeçalho central, foto contain, seleção de dois exemplares, imagem da Dashboard e módulos antigos preservados.
- MSFS real: selecionar no Hangar, trocar foto, reabrir app, conferir Dashboard e combustível/desgaste, cancelar troca sem alterar dados, verificar custo de revisão em solo e bloqueio em voo.

Banco criado sem migração destrutiva; sempre fazer backup do `carreira.db` com o app fechado.
