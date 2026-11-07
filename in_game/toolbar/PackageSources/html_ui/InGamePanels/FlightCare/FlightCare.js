/* FlightSim InGame Alpha.3 — native MSFS 2020 toolbar lifecycle.
 * Only Coherent owns the outer titlebar. Never synthesize a drag by touching
 * mouse events inside the localhost iframe; it would move only its content.
 */
class FlightCareToolbar extends TemplateElement {
  constructor() {
    super(...arguments);
    this.ingameUi = null;
    this.panelActive = false;
    this.eventsBound = false;
  }

  connectedCallback() {
    super.connectedCallback();
    this.ingameUi = this.querySelector('ingame-ui');
    if (this.ingameUi && !this.eventsBound) {
      this.eventsBound = true;
      this.ingameUi.addEventListener('panelActive', () => {
        this.panelActive = true;
        this.restoreNativeHeader();
      });
      this.ingameUi.addEventListener('panelInactive', () => {
        this.panelActive = false;
      });
      this.ingameUi.addEventListener('panelReady', () => {
        if (this.panelActive) this.restoreNativeHeader();
      });
    }
    this.initialize();
  }

  initialize() {
    // MSFS applies its draggable panel classes asynchronously. Avoid
    // removing panelInvisible from a closed 2020 panel.
    window.setTimeout(() => this.restoreNativeHeader(), 900);
  }

  restoreNativeHeader() {
    const panel = this.ingameUi || document.getElementById('FlightSimCarreira');
    if (!panel) return;

    // 2024 compatibility workaround, only if the SDK inserted "hide".
    if (panel.classList.contains('hide')) {
      panel.classList.remove('hide');
      panel.classList.remove('panelInvisible');
    }
    if (this.panelActive) {
      // The 2020 ingameUiFrame is made moveable through its own titlebar
      // when active, not through the frame's web page.
      panel.classList.remove('panelInvisible');
      panel.classList.add('draggable');
      panel.setAttribute('title', 'FlightSim');
    }
  }
}
customElements.define('ingamepanel-flightcare', FlightCareToolbar);
checkAutoload();
