/* Protótipo de painel: sem comandos de voo, sem ações financeiras, sem dependências externas. */
class FlightCareToolbar extends TemplateElement {
  constructor() { super(...arguments); }
  connectedCallback() { super.connectedCallback(); }
  initialize() {}
}
customElements.define('ingamepanel-flightcare',FlightCareToolbar);
checkAutoload();
