"""Carregamento VFR deve ocorrer no worker, nunca por callback Tk."""
import sys
import time
import types
import unittest
from pathlib import Path
from queue import Queue,Empty
from tempfile import TemporaryDirectory
from unittest.mock import patch
from aerocarreira.flightplan import export_vfr_plan
from aerocarreira.domain import MISSIONS
from aerocarreira.sim_adapter import SimConnectWorker, REQUIRED


class WorkerPlanTests(unittest.TestCase):
    def test_load_plan_queued_and_worker_reports_only_api_acceptance(self):
        loaded=[]
        class Conn:
            quit=False
            def load_flight_plan(self,path):
                loaded.append(path)
                return True
            def exit(self):pass
        class Req:
            def __init__(self,sm,_time=200):pass
            def get(self,key):
                table={key:0 for key in REQUIRED.values()}
                table.update({'PLANE_LATITUDE':-7.656,'PLANE_LONGITUDE':-34.856,
                    'SIM_ON_GROUND':1,'AIRSPEED_INDICATED':0})
                return table.get(key)
        fake=types.ModuleType('SimConnect')
        fake.SimConnect=Conn
        fake.AircraftRequests=Req
        with TemporaryDirectory() as folder:
            path=export_vfr_plan(MISSIONS[-1],folder)
            q=Queue()
            with patch.dict(sys.modules,{'SimConnect':fake}):
                worker=SimConnectWorker(q,interval=0.01,reconnect_delay=0.01)
                worker.start()
                worker.request_plan_load(path)
                msgs=[]
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    try:
                        event=q.get(timeout=.04)
                        msgs.append(event)
                        if event[0]=='plan_atc_sent':break
                    except Empty:pass
                worker.stop();worker.thread.join(timeout=2)
            self.assertEqual(loaded,[str(path)])
            self.assertTrue(any(x[0]=='plan_atc_sent' and 'ATC' in x[1] for x in msgs),msgs)

    def test_does_not_load_untrusted_file_extension(self):
        called=[]
        class Conn:
            quit=False
            def load_flight_plan(self,path):called.append(path);return True
            def exit(self):pass
        class Req:
            def __init__(self,*a,**kw):pass
            def get(self,key):return 1.0 if key=='SIM_ON_GROUND' else 0.0
        fake=types.ModuleType('SimConnect');fake.SimConnect=Conn;fake.AircraftRequests=Req
        with TemporaryDirectory() as folder:
            file=Path(folder)/'evil.txt';file.write_text('not a plan')
            q=Queue()
            with patch.dict(sys.modules,{'SimConnect':fake}):
                worker=SimConnectWorker(q,interval=.01,reconnect_delay=.01)
                worker.start();worker.request_plan_load(file)
                deadline=time.monotonic()+2
                found=False
                while time.monotonic()<deadline:
                    try:
                        event=q.get(timeout=.04)
                        if event[0]=='plan_error':found=True;break
                    except Empty:pass
                worker.stop();worker.thread.join(timeout=2)
            self.assertTrue(found)
            self.assertEqual(called,[])

if __name__=='__main__':unittest.main()
