"""Launch the REAL Application against an isolated, explicitly labelled QA career."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['FLIGHTSIM_HEADLESS']='1'
from aerocarreira.app import Application
from aerocarreira.domain import MISSIONS
app=Application()
app.storage.create_pilot('Piloto de teste automatizado','QA-DEMO','SBRF')
app.storage.claim_starter();app.storage.fleet_manager().select('legacy:c152')
app._refresh_pilot_summary();app._demo_start();app._accept_specific(MISSIONS[0])
app._log('QA AUTOMATIZADO • carreira temporária • nenhuma informação pessoal.')
app.dashboard.server.publish(app.dashboard.presenter.snapshot())
Path(sys.argv[1]).write_text(app.dashboard.server.url)
app.run()
