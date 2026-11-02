"""MSFS 2020 SimConnect: leitura tolerante a dados ausentes e reconexão automática.

Dependência opcional importada no worker; não modifica o simulador.
"""
from __future__ import annotations
from queue import Queue
from threading import Thread, Event
from time import time
from .domain import FlightSample

# SimVars sem as quais NÃO é seguro produzir uma amostra de posição/solo.
REQUIRED = {
    "latitude": "PLANE_LATITUDE",
    "longitude": "PLANE_LONGITUDE",
    "altitude_ft": "PLANE_ALTITUDE",
    "agl_ft": "PLANE_ALT_ABOVE_GROUND",
    "ias_kt": "AIRSPEED_INDICATED",
    "on_ground": "SIM_ON_GROUND",
}
# Uma única ausência de GROUND_VELOCITY NÃO derruba a sessão.
SOFT = {"groundspeed_kt": "GROUND_VELOCITY", "vs_fpm": "VERTICAL_SPEED"}
OPTIONAL = {"stall_warning": "STALL_WARNING", "fuel_gallons": "FUEL_TOTAL_QUANTITY"}


class SampleReader:
    """Pura lógica testável; lê somente SimVars, sem persistir/forçar estado do MSFS."""
    def __init__(self, requests, clock=time):
        self.requests = requests
        self.clock = clock
        self.last = None
        self.last_groundspeed_time = None
        self.soft_missing = set()

    def _get(self, simvar):
        try:
            value = self.requests.get(simvar)
            return None if value is None else float(value)
        except (ValueError, TypeError, KeyError, OSError, RuntimeError):
            return None

    def read(self):
        values = {key: self._get(var) for key, var in REQUIRED.items()}
        missing = [REQUIRED[key] for key, val in values.items() if val is None]
        if missing:
            return None, missing
        now = self.clock()
        self.soft_missing = set()
        gs = self._get(SOFT["groundspeed_kt"])
        estimated = gs is None
        if gs is None:
            self.soft_missing.add("GROUND_VELOCITY")
            if self.last and self.last_groundspeed_time is not None and now - self.last_groundspeed_time < 5:
                gs = self.last.groundspeed_kt
            else:
                # Somente para telemetria ilustrativa/limiar de decolagem;
                # nunca afirmar que IAS == velocidade real sobre o solo.
                gs = values["ias_kt"]
        else:
            self.last_groundspeed_time = now
        vs = self._get(SOFT["vs_fpm"])
        if vs is None:
            self.soft_missing.add("VERTICAL_SPEED")
            vs = self.last.vs_fpm if self.last and now - self.last.timestamp < 5 else 0.0
        stall = self._get(OPTIONAL["stall_warning"])
        fuel = self._get(OPTIONAL["fuel_gallons"])
        s = FlightSample(timestamp=now,
            latitude=values["latitude"], longitude=values["longitude"],
            altitude_ft=values["altitude_ft"], agl_ft=values["agl_ft"],
            ias_kt=values["ias_kt"], groundspeed_kt=gs,
            vs_fpm=vs, on_ground=values["on_ground"] >= 0.5,
            fuel_gallons=fuel, stall_warning=None if stall is None else stall >= 0.5,
            groundspeed_estimated=estimated)
        self.last = s
        return s, []


class SimConnectWorker:
    """Mantém a conexão: um erro intermitente não finaliza o monitoramento.

    Mensagens incluem ID de geração para descartar eventos de sessões antigas.
    """
    def __init__(self, outgoing: Queue, interval: float = 0.5, generation: int = 0,
                 reconnect_delay: float = 3.0):
        self.outgoing = outgoing
        self.interval = interval
        self.generation = generation
        self.reconnect_delay = reconnect_delay
        self.stop_event = Event()
        self.thread = None

    def _send(self, kind, value):
        self.outgoing.put((kind, value, self.generation))

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = Thread(target=self._run, name="simconnect-reader", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self):
        try:
            from SimConnect import SimConnect, AircraftRequests
        except Exception as exc:
            self._send("error", f"SimConnect indisponível: {exc}. Verifique a instalação do adaptador.")
            self._send("disconnected", "Adaptador não instalado")
            return
        while not self.stop_event.is_set():
            sm = None
            try:
                sm = SimConnect()
                aq = AircraftRequests(sm, _time=200)
                reader = SampleReader(aq)
                self._send("connected", "SimConnect conectado")
                missing_runs = 0
                last_warning = 0.0
                while not self.stop_event.is_set():
                    if getattr(sm, "quit", False):
                        raise ConnectionError("O simulador encerrou a sessão SimConnect")
                    sample, missing = reader.read()
                    now = time()
                    if sample is None:
                        missing_runs += 1
                        if now - last_warning >= 8:
                            self._send("warning", "Telemetria temporariamente incompleta: " + ", ".join(missing))
                            last_warning = now
                        # Várias leituras críticas consecutivas sem retorno indicam sessão quebrada.
                        if missing_runs >= 30:
                            raise ConnectionError("Sem dados críticos por 30 ciclos; recriando conexão")
                    else:
                        missing_runs = 0
                        self._send("sample", sample)
                        if reader.soft_missing and now - last_warning >= 15:
                            self._send("warning", "SimVar intermitente: " + ", ".join(sorted(reader.soft_missing)) + "; monitoramento continua")
                            last_warning = now
                    self.stop_event.wait(self.interval)
            except Exception as exc:
                if not self.stop_event.is_set():
                    self._send("warning", f"Conexão interrompida: {exc}. Tentando reconectar...")
            finally:
                if sm is not None:
                    try:
                        sm.exit()
                    except Exception:
                        pass
                if not self.stop_event.is_set():
                    self._send("disconnected", "Reconectando automaticamente...")
            self.stop_event.wait(self.reconnect_delay)
        self._send("disconnected", "SimConnect desconectado")
