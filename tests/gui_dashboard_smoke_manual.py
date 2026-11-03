"""Run on Windows or xvfb: python tests/gui_dashboard_smoke_manual.py"""
from pathlib import Path
from unittest.mock import patch
from aerocarreira.app import Application
from aerocarreira.domain import MISSIONS, FlightSample
import tempfile

with tempfile.TemporaryDirectory() as d:
    with patch('aerocarreira.app.state_dir',return_value=Path(d)):
        app=Application()
        app.storage.create_pilot('Piloto Teste','BM2564','SBRF')
        app._refresh_pilot_summary()
        app.ui.refresh(force_market=True)
        app.root.update_idletasks()
        app.root.update()
        assert app.ui.pilot_text.get() == 'BM2564'
        assert app.ui.market_airport.get().startswith('SBRF')
        assert 0 < len(app.ui.market_offers) <= 13
        assert app.ui.map_canvas.winfo_width() >= 480
        app.career.accept(MISSIONS[0])
        app._show_mission()
        app.ui.refresh()
        app.root.update()
        assert 'SBRF' in app.ui.mission_route.get()
        assert len(app.ui.map_canvas.find_all())>20
        # Existing telemetry vars remain usable with the new dashboard.
        app.flight_vars['ias'].set('80')
        assert app.flight_vars['ias'].get()=='80'
        # Settings and logbook are real windows.
        app.ui.open_settings();app.ui.open_logbook()
        app.root.update()
        app._close()
        print('Dashboard GUI smoke OK')
