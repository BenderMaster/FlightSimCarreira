/* FlightSim InGame Alpha.4 — MSFS 2020 native ingame-ui panel lifecycle.
 * Do not add .draggable or remove .panelInvisible manually in FS2020;
 * the Coherent ingame-ui template and toolbar own visibility and move/resize.
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
        this.reportPanelGeometry('active');
      });
      this.ingameUi.addEventListener('panelInactive', () => {
        this.panelActive = false;
      });
      this.ingameUi.addEventListener('panelReady', () => {
        this.reportPanelGeometry('ready');
      });
      this.ingameUi.addEventListener('onResizeElement', () => {
        this.reportPanelGeometry('resize');
      });
    }
    this.initialize();
  }
  initialize() {
    // FS2024-only workaround: 2020 deliberately preserves panelInvisible.
    // Do not touch 2020 frame classes or override native header hit testing.
    window.setTimeout(() => {
      const panel = this.ingameUi || document.getElementById('FlightSimCarreira');
      if (panel && panel.classList.contains('hide')) {
        panel.classList.remove('hide');
        panel.classList.remove('panelInvisible');
        panel.setAttribute('title', 'FlightSim');
      }
    }, 900);
  }
  reportPanelGeometry(source) {
    // Debug diagnostics when requested, no tokens, careers or private data.
    const panel = this.ingameUi;
    if (!panel) return;
    const iframe = document.getElementById('flightSimFrame');
    const content = panel.querySelector('.ingameUiContent');
    console.info('[FlightSim-InGame] ' + source, {
      frame: Math.round(panel.getBoundingClientRect().height),
      content: content ? Math.round(content.getBoundingClientRect().height) : -1,
      iframe: iframe ? Math.round(iframe.getBoundingClientRect().height) : -1,
      classes: panel.className,
      title: panel.getAttribute('title')
    });
  }
}
window.customElements.define('ingamepanel-flightcare', FlightCareToolbar);
checkAutoload();
