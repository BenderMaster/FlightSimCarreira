# FlightSim v0.9.2 InGame Alpha.1 — roteiro de teste

**Branch:** \`feature/v0.9.2-ingame-complete-operations\` (base v0.9.1 Alpha.1).  
**Status:** implementação e testes automatizados; **homologação física MSFS 2020 Steam pendente**.  
**Não mesclar na main sem aprovação.**

## Downloads

Na execução final do GitHub Actions desta branch:

- \`FlightSim-0.9.2-ingame-alpha1-Windows\`: extrair integralmente para uma pasta nova. Executar \`FlightSim.exe\`; não precisa abrir CMD.
- \`FlightSim-InGame-0.9.2-SDK-Source\`: os arquivos Community são **fonte SDK**, não pacote SPB pronto. **Não houve alteração no wrapper da toolbar** em relação à v0.9.1 — se o seu painel já está compilado, instalado na Community e abrindo corretamente, **não precisa recompilar o package**. Atualizar somente o executável Windows já altera o conteúdo servido pelo iframe em \`127.0.0.1:8769\`.

Caso ainda não tenha instalado o pacote, habilite Developer Mode, abra \`in_game/toolbar/package.xml\` no Project Editor, configure Creator \`FlightSim\`, Company \`flightsim\`, Content-Type \`MISC\`; use **Build All**. Copie só o pacote final com \`manifest.json\`, \`layout.json\`, \`.spb\` e \`html_ui\` para Community (localize em Tools > Virtual File System > Packages Folders > Open Community Folder). Reinicie o MSFS.

## Telas v0.9.2

1. **Painel / Mercado:** continuam os dados SimConnect e contratos da v0.9.1.
2. **Planejar:** ICAOs verificados, altitude 500–45000 ft, waypoints até 8, checklist. Salvar, limpar, exportar .PLN e enviar para o MSFS. Envio de plano e carga dependem do SimConnect; o GPS/VFR não é automaticamente sincronizado em todos os aviões.
3. **Hangar:** cards, fotos de aviões próprias quando cadastradas, imagens showroom para modelos clássicos, seleção de exemplar, revisão, seguro, compras, usadas, aluguel (24/48/72/168 h) e venda. Toda ação financeira requer solo e aeroportos elegíveis.
4. **Empresas:** vínculos, metas, candidaturas, trechos profissionais, treinamento, empresa própria. A seleção continua obedecendo a janela semanal de 7 dias reais; receitas/salários não são fabricados pelo tablet.
5. **Carreira:** piloto, patente, reputação, XP, licenças elegíveis e conquistas.
6. **Logbook:** histórico e anotações por voo. A operação não modifica recompensas ou telemetria antiga.
7. **Finanças:** receitas, despesas, dívida, empréstimos, amortizações, seguro e gráfico mensal baseado no ledger existente.

A interface usa os módulos locais \`in_game/office-ui.js\`, \`office-ui.css\`, \`office-nav.html\` e \`office-pages.html\`. Nenhuma API de mapas, imagem ou compra externa é obrigatória.

## Reteste físico no MSFS

- [ ] O aplicativo Windows inicia **sem CMD** e \`http://127.0.0.1:8769/\` carrega as dez páginas sem erros.
- [ ] O título nativo **FLIGHTSIM** continua movível; redimensionamento não introduz área cinza.
- [ ] Acentos **Planejamento, Aviação, Operações, Aeronave e Próxima** continuam legíveis.
- [ ] Mercado/Contrato da v0.9.1 não regrediu.
- [ ] Salvar Plano e enviar .PLN ao MSFS funciona e exibe retorno após confirmação do motor.
- [ ] As ofertas de Hangar são reais do mercado simulado e correspondem ao aeroporto MSFS da sessão; compras/seguros são debitados **uma única vez**.
- [ ] Sem voo ativo, uma candidatura elegível é enviada; em voo ou com contrato ativo, operações proibidas são bloqueadas.
- [ ] Licenças mostram requisitos corretos e só são concedidas se o backend confirmar.
- [ ] Logbook salva uma anotação, que sobrevive ao reinício.
- [ ] Finanças mostram o mesmo saldo, ledger, dívida e patrimônio da versão Windows. Testar empréstimo apenas em perfil de teste.
- [ ] Alterar o tamanho da janela não impede clicar nos botões e rolar o menu lateral/inferior.
- [ ] Comparar FPS no mesmo cenário com painel fechado/aberto e durante transações.

**Testar operações financeiras somente em uma carreira de teste ou após backup.** O motor usa o banco real da carreira ativa, inclusive no MSFS.

## Limites conhecidos da Alpha

- O painel Community não inicia o executável Windows automaticamente: mantenha FlightSim.exe aberto. Iniciar como companheiro sem janela/área de notificação é uma etapa própria.
- O mapa do tablet ainda é o SVG de contingência. A v0.9.2 permite waypoints na lista, mas não substitui o mapa completo MapLibre do desktop, nem altera o VFR oficial.
- Fotos personalizadas são lidas do SQLite do perfil ativo e servidas como miniaturas locais por sessão; upload da foto continua no Windows.
- Perfil/piloto é consultável no tablet; troca de carreira com reinicialização segura, restaurar backups, fotos via seletor de arquivos e exportar extratos via diálogo Windows ainda permanecem no desktop.
- Ações assíncronas de combustível/plano podem ter um recibo "comando enviado" antes de a aeronave refletir o ajuste. É necessário conferir as leituras seguintes do SimConnect.

### Diagnóstico

Em problemas de renderização, a ponte HTTP permanece acessível em \`http://127.0.0.1:8769/api/v1/health\`.
No Developer Mode, consulte **Debug > Console** e o Coherent Debugger.
Não desabilite CORS, CSP, autenticação ou validações da carreira para forçar a página a carregar. O motor nunca envia credenciais fixas à Community.

## Código

- \`aerocarreira/ingame_office.py\` — projeção de dados limitada, na thread principal.
- \`aerocarreira/ingame_bridge.py\` — servidor local, token de leitura/comando, media JPEG e CSRF.
- \`aerocarreira/app.py\` — validação final e execução de comandos na thread Tk.
- \`in_game/office-ui.js\` / \`office-ui.css\` — interface, sem autoridade sobre SQLite.
- \`tests/test_ingame_v092.py\`, \`scripts/verify_ingame.py\` — regressões, UX e segurança.
