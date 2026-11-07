/* FlightSim v0.9.0: SDK toolbar wrapper. No financial actions or data access.
 * Business logic stays in Python; read-only dashboard runs in loopback iframe.
 * The fixed port is not an authentication credential.
 */
class FlightCareToolbar extends TemplateElement {
  constructor() { super(...arguments); }
  connectedCallback() { super.connectedCallback(); }
  initialize() {}
}
customElements.define('ingamepanel-flightcare', FlightCareToolbar);
checkAutoload();
