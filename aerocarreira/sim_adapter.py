"""Adaptador de telemetria somente leitura para MSFS2020; Windows e SimConnect.

A biblioteca SimConnect é dependência opcional, importada só ao conectar.
Nenhuma chamada muda variáveis ou envia eventos para o simulador.
"""
from __future__ import annotations
from dataclasses import dataclass
from queue import Queue
from threading import Thread, Event
from time import sleep, time
from .domain import FlightSample


FIELDS = {
    "latitude": "PLANE_LATITUDE",
    "longitude": "PLANE_LONGITUDE",
    "altitude_ft": "PLANE_ALTITUDE",
    "agl_ft": "PLANE_ALT_ABOVE_GROUND",
    "ias_kt": "AIRSPEED_INDICATED",
    "groundspeed_kt": "GROUND_VELOCITY",
    "vs_fpm": "VERTICAL_SPEED",
    "on_ground": "SIM_ON_GROUND",
}
OPTIONAL_FIELDS = {
    "stall_warning": "STALL_WARNING",
    "fuel_gallons": "FUEL_TOTAL_QUANTITY",
}


class SimConnectWorker:
    def __init__(self, outgoing: Queue, interval: float = 0.4):
        self.outgoing = outgoing
        self.interval = interval
        self.stop_event = Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = Thread(target=self._run, name="simconnect-reader", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self):
        sm = None
        try:
            from SimConnect import SimConnect, AircraftRequests
            sm = SimConnect()
            aq = AircraftRequests(sm, _time=200)
            self.outgoing.put(("connected", "SimConnect conectado"))
            while not self.stop_event.is_set() and not getattr(sm, "quit", False):
                values = {}
                for key, simvar in FIELDS.items():
                    value = aq.get(simvar)
                    if value is None:
                        raise RuntimeError(f"SimVar sem resposta: {simvar}")
                    values[key] = float(value)
                opt = {}
                for key, simvar in OPTIONAL_FIELDS.items():
                    try:
                        read = aq.get(simvar)
                        opt[key] = None if read is None else float(read)
                    except Exception:
                        opt[key] = None
                s = FlightSample(
                    timestamp=time(),
                    latitude=values["latitude"], longitude=values["longitude"],
                    altitude_ft=values["altitude_ft"], agl_ft=values["agl_ft"],
                    ias_kt=values["ias_kt"], groundspeed_kt=values["groundspeed_kt"],
                    vs_fpm=values["vs_fpm"], on_ground=values["on_ground"] >= 0.5,
                    fuel_gallons=opt["fuel_gallons"],
                    stall_warning=None if opt["stall_warning"] is None else opt["stall_warning"] >= 0.5)
                self.outgoing.put(("sample", s))
                self.stop_event.wait(self.interval)
        except Exception as exc:
            self.outgoing.put(("error", f"Falha SimConnect: {exc}"))
        finally:
            if sm is not None:
                try: sm.exit()
                except Exception: pass
            self.outgoing.put(("disconnected", "SimConnect desconectado"))
