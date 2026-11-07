/* FlightSim v0.9.0: SDK toolbar wrapper. No financial actions or data access.
 * Business logic stays in Python; read-only dashboard runs in loopback iframe.
 * The fixed port is not an authentication credential.
 */
class FlightCareToolbar extends TemplateElement {
  constructor() { super(...arguments); }
  connectedCallback() { super.connectedCallback(); }
  initialize() {
    // Preserve the MSFS 2020-managed titlebar and dragging. The 2024
    // compatibility workaround only applies when Coherent injects "hide".
    const restoreTitle = () => {
      const p = document.getElementById('FlightSimCarreira');
      if (p && p.classList.contains('hide')) {
        p.classList.remove('hide');
        p.classList.remove('panelInvisible');
        p.title = 'FlightSim';
      }
    };
    window.setTimeout(restoreTitle, 800);
  }
}
customElements.define('ingamepanel-flightcare', FlightCareToolbar);
checkAutoload();
