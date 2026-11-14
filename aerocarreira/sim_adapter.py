"""MSFS 2020 SimConnect: leitura tolerante a dados ausentes e reconexão automática.

Dependência opcional importada no worker; não modifica o simulador.
"""
from __future__ import annotations
from queue import Queue, Empty
from threading import Thread, Event
from time import time
from math import degrees, isfinite
from .domain import FlightSample
from .contracts import aircraft_model
from .fuel import TANK_QUANTITY, TANK_CAPACITY

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
OPTIONAL = {"stall_warning": "STALL_WARNING", "fuel_gallons": "FUEL_TOTAL_QUANTITY",
            "total_weight_lbs": "TOTAL_WEIGHT", "max_gross_weight_lbs": "MAX_GROSS_WEIGHT",
            "wind_kt": "AMBIENT_WIND_VELOCITY", "ambient_temperature_c": "AMBIENT_TEMPERATURE",
            "sim_rate": "SIMULATION_RATE", "unlimited_fuel":"UNLIMITED_FUEL",
            "wind_direction_deg":"AMBIENT_WIND_DIRECTION",
            "visibility_m":"AMBIENT_VISIBILITY",
            "sea_level_pressure_hpa":"SEA_LEVEL_PRESSURE",
            "heading_true_rad":"PLANE_HEADING_DEGREES_TRUE",
            "heading_magnetic_rad":"PLANE_HEADING_DEGREES_MAGNETIC",
            "on_any_runway":"ON_ANY_RUNWAY",
            "atc_on_parking_spot":"ATC_ON_PARKING_SPOT",
            "plane_in_parking_state":"PLANE_IN_PARKING_STATE",
            "parking_brake_set":"BRAKE_PARKING_POSITION",
            "assistance_landing":"ASSISTANCE_LANDING_ENABLED",
            "assistance_takeoff":"ASSISTANCE_TAKEOFF_ENABLED",
            "ai_controls":"AI_CONTROLS",
            "zulu_time_s":"ZULU_TIME",
            "light_beacon":"LIGHT_BEACON",
            "light_nav":"LIGHT_NAV",
            "light_taxi":"LIGHT_TAXI",
            "light_landing":"LIGHT_LANDING",
            "light_strobe":"LIGHT_STROBE",
            "engine_running":"GENERAL_ENG_COMBUSTION:1",
            "g_force":"G_FORCE"}



def true_heading_degrees(radians):
    """SimVar PLANE HEADING DEGREES TRUE usa radianos (SDK/MSFS).

    Não usar track/GPS: orientação do nariz muda até com avião parado no solo.
    """
    if radians is None:
        return None
    try:
        value=float(radians)
    except (ValueError,TypeError,OverflowError):
        return None
    return degrees(value)%360.0 if isfinite(value) else None


class SampleReader:
    """Pura lógica testável; lê somente SimVars, sem persistir/forçar estado do MSFS."""
    def __init__(self, requests, clock=time):
        self.requests = requests
        self.clock = clock
        self.last = None
        self.last_groundspeed_time = None
        self.soft_missing = set()
        self.last_tank_scan = -1e15
        self.last_payload_scan = -1e15

    def _get(self, simvar):
        try:
            value = self.requests.get(simvar)
            return None if value is None else float(value)
        except (ValueError, TypeError, KeyError, OSError, RuntimeError):
            return None

    def _title(self):
        try:
            value = self.requests.get("TITLE")
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            return value.strip() if isinstance(value, str) and value.strip() else None
        except (ValueError, TypeError, KeyError, OSError, RuntimeError):
            return None

    def _tank_snapshot(self, title, now):
        """Máximo 1 consulta a cada 3 segundos; ausências nunca são inventadas."""
        if now-self.last_tank_scan < 3.0:
            return None,None
        self.last_tank_scan=now
        model=aircraft_model(title)
        tank_sets={
            'c152':('LEFT_MAIN','RIGHT_MAIN'),
            'c172':('LEFT_MAIN','RIGHT_MAIN'),
            'g58':('LEFT_MAIN','RIGHT_MAIN','LEFT_AUX','RIGHT_AUX'),
            'kingair':('LEFT_MAIN','RIGHT_MAIN','CENTER','LEFT_AUX','RIGHT_AUX'),
            'cj4':('LEFT_MAIN','RIGHT_MAIN','CENTER'),
        }
        names=tank_sets.get(model,())
        if not names:
            return None,None
        tanks={}
        caps={}
        for name in names:
            q=self._get(TANK_QUANTITY[name]); cap=self._get(TANK_CAPACITY[name])
            if q is None or cap is None or cap <= 0:
                continue
            tanks[name]=q
            caps[name]=cap
        return (tanks or None),(caps or None)

    def _payload_snapshot(self, now):
        if now-self.last_payload_scan<2.5:
            return None,None
        self.last_payload_scan=now
        count=self._get("PAYLOAD_STATION_COUNT")
        if count is None or not isfinite(count) or not 2<=count<=15:
            return None,None
        n=int(count)
        values={}
        for i in range(1,n+1):
            v=self._get("PAYLOAD_STATION_WEIGHT:"+str(i))
            if v is None or not isfinite(v) or not 0<=v<=15000:
                return None,None
            values[i]=v
        return n,values

    def _optional_bool(self,key):
        value=self._get(OPTIONAL[key])
        return None if value is None or not isfinite(value) else value>=0.5

    def _engines_running(self, title):
        """All installed engines must be verified off before payout.

        If engine count is missing, use a proven fixed count for known
        economy models; unknown models remain unverified rather than
        treating engine #1 as all engines.
        """
        count=self._get('NUMBER_OF_ENGINES')
        if count is None or not isfinite(count) or not 1<=count<=4 or int(count)!=count:
            count={'c152':1,'c172':1,'g58':2,'kingair':2,'cj4':2}.get(aircraft_model(title))
        if count is None:return None
        flags=[]
        for index in range(1,int(count)+1):
            value=self._get('GENERAL_ENG_COMBUSTION:'+str(index))
            if value is None or not isfinite(value):return None
            flags.append(value>=0.5)
        return any(flags)

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
        title = self._title()
        tanks,cap = self._tank_snapshot(title,now)
        station_count,station_weights=self._payload_snapshot(now)
        s = FlightSample(timestamp=now,
            latitude=values["latitude"], longitude=values["longitude"],
            altitude_ft=values["altitude_ft"], agl_ft=values["agl_ft"],
            ias_kt=values["ias_kt"], groundspeed_kt=gs,
            vs_fpm=vs, on_ground=values["on_ground"] >= 0.5,
            fuel_gallons=fuel, stall_warning=None if stall is None else stall >= 0.5,
            groundspeed_estimated=estimated, aircraft_title=title,
            total_weight_lbs=self._get(OPTIONAL['total_weight_lbs']),
            max_gross_weight_lbs=self._get(OPTIONAL['max_gross_weight_lbs']),
            payload_station_count=station_count,
            payload_station_weights=station_weights,
            wind_kt=self._get(OPTIONAL['wind_kt']),
            ambient_temperature_c=self._get(OPTIONAL['ambient_temperature_c']),
            wind_direction_deg=self._get(OPTIONAL['wind_direction_deg']),
            visibility_m=self._get(OPTIONAL['visibility_m']),
            sea_level_pressure_hpa=self._get(OPTIONAL['sea_level_pressure_hpa']),
            heading_true_deg=true_heading_degrees(self._get(OPTIONAL['heading_true_rad'])),
            heading_magnetic_deg=true_heading_degrees(self._get(OPTIONAL['heading_magnetic_rad'])),
            on_any_runway=self._optional_bool('on_any_runway'),
            atc_on_parking_spot=self._optional_bool('atc_on_parking_spot'),
            plane_in_parking_state=self._optional_bool('plane_in_parking_state'),
            parking_brake_set=self._optional_bool('parking_brake_set'),
            sim_rate=self._get(OPTIONAL['sim_rate']),
            fuel_tanks=tanks, fuel_tank_capacities=cap,
            unlimited_fuel=self._optional_bool('unlimited_fuel'),
            engine_running=self._engines_running(title),
            assistance_landing=self._optional_bool('assistance_landing'),
            assistance_takeoff=self._optional_bool('assistance_takeoff'),
            ai_controls=self._optional_bool('ai_controls'),
            zulu_time_s=self._get(OPTIONAL['zulu_time_s']),
            light_beacon=self._optional_bool('light_beacon'),
            light_nav=self._optional_bool('light_nav'),
            light_taxi=self._optional_bool('light_taxi'),
            light_landing=self._optional_bool('light_landing'),
            light_strobe=self._optional_bool('light_strobe'),
            g_force=self._get(OPTIONAL['g_force']))
        self.last = s
        return s, []


class SimConnectWorker:
    """Mantém a conexão: um erro intermitente não finaliza o monitoramento.

    Mensagens incluem ID de geração para descartar eventos de sessões antigas.
    """
    def __init__(self, outgoing: Queue, interval: float = 0.5, generation: int = 0,
                 reconnect_delay: float = 3.0, reconnect: bool = True):
        self.outgoing = outgoing
        self.interval = interval
        self.generation = generation
        self.reconnect_delay = reconnect_delay
        self.reconnect = reconnect
        self.actions = Queue()
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

    def request_airports(self, codes=()):
        """Compatibilidade: sempre consulta a lista INTEIRA do MSFS 2020.

        Códigos do catálogo externo nunca entram na consulta nem na oferta.
        """
        self.actions.put(('airports',None))

    def request_plan_load(self, path):
        """Somente sob clique explícito e com o simulador conectado."""
        self.actions.put(("load_pln", str(path)))

    def request_payload_set(self, mission_id, stations: dict[int,float]):
        if not isinstance(mission_id,str) or not mission_id or len(mission_id)>130:
            raise ValueError('Identificador de missão inválido')
        if not stations or len(stations)>14 or any(
                not isinstance(k,int) or not 2<=k<=15 or
                not isinstance(v,(int,float)) or not isfinite(v) or not 0<=v<=15000
                for k,v in stations.items()):
            raise ValueError('Distribuição de peso inválida')
        self.actions.put(('payload_set',{'mission':mission_id,'stations':dict(stations)}))

    def request_fuel_restore(self, tanks: dict[str,float]):
        """Comando gerado por FuelManager; não recebe SimVar arbitrária."""
        if not tanks or any(k not in TANK_QUANTITY for k in tanks):
            raise ValueError('Tanque inválido')
        self.actions.put(('fuel_restore',dict(tanks)))

    def stop(self):
        self.stop_event.set()

    def _run(self):
        try:
            from SimConnect import SimConnect, AircraftRequests
            from .sim_facilities import connection_class
        except Exception as exc:
            self._send("error", f"SimConnect indisponível: {exc}. Verifique a instalação do adaptador.")
            self._send("disconnected", "Adaptador não instalado")
            return
        while not self.stop_event.is_set():
            sm = None
            try:
                try:
                    sm=connection_class()(
                        lambda airports:self._send('airport_catalog',airports),
                        lambda error:self._send('airport_catalog_error',error))
                except (AttributeError,OSError,ValueError,RuntimeError) as exc:
                    sm=SimConnect()  # mantém monitor, mas NÃO libera mercado
                    self._send('airport_catalog_error','Listagem MSFS indisponível: '+str(exc))
                aq = AircraftRequests(sm, _time=200)
                reader = SampleReader(aq)
                self._send("connected", "SimConnect conectado")
                # Consulta mundial de aeroportos é potencialmente custosa.
                # Não pedir enquanto o MSFS ainda está carregando o voo,
                # nem em pleno voo. Fazer no máximo UMA solicitação por sessão,
                # após 3 s de amostras estáveis com aeronave em solo.
                catalog_attempted = False
                ground_since = None
                missing_runs = 0
                last_warning = 0.0
                while not self.stop_event.is_set():
                    try:
                        while True:
                            action, path = self.actions.get_nowait()
                            if action=='airports':
                                # Pedido pendente é atendido quando o MSFS
                                # estiver carregado e a aeronave em solo.
                                # Nunca pedir múltiplos catálogos mundiais.
                                pass
                            if action == 'fuel_restore':
                                # Ações de escrita somente pela thread SimConnect.
                                # Settable: quantidades individuais; total é read-only.
                                try:
                                    for tank, amount in path.items():
                                        if tank not in TANK_QUANTITY or not (0 <= amount <= 20000):
                                            raise ValueError('Quantidade de tanque inválida')
                                        result=aq.set(TANK_QUANTITY[tank],float(amount))
                                        if result is False:
                                            raise ValueError('SimConnect recusou escrita em '+tank)
                                    self._send('fuel_sent','Correção dos tanques enviada; aguardando confirmação da leitura.')
                                except (AttributeError,OSError,ValueError,RuntimeError) as exc:
                                    self._send('fuel_error',str(exc))
                            if action=='payload_set':
                                try:
                                    for index,pounds in path['stations'].items():
                                        ok=aq.set('PAYLOAD_STATION_WEIGHT:'+str(index),float(pounds))
                                        if ok is False:
                                            raise ValueError('MSFS recusou estação '+str(index))
                                    self._send('payload_sent',path['mission'])
                                except (AttributeError,OSError,ValueError,RuntimeError) as exc:
                                    self._send('payload_error',str(exc))
                            if action == 'load_pln':
                                from pathlib import Path
                                file = Path(path)
                                if not file.is_file() or file.suffix.lower() != '.pln':
                                    self._send('plan_error', 'Plano VFR inválido ou inexistente.')
                                else:
                                    try:
                                        # O adaptador Python-SimConnect implementa esta API do SDK.
                                        accepted = sm.load_flight_plan(str(file))
                                        if accepted:
                                            self._send('plan_atc_sent', f'Plano enviado ao ATC do MSFS: {file.name}. O mapa VFR/GPS NÃO é sincronizado pelo SimConnect do MSFS 2020.')
                                        else:
                                            self._send('plan_error', 'SimConnect recusou a solicitação de plano VFR.')
                                    except (OSError, AttributeError, ValueError, RuntimeError) as exc:
                                        self._send('plan_error', f'Falha ao solicitar plano VFR: {exc}')
                    except Empty:
                        pass
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
                        if sample.on_ground:
                            if ground_since is None:
                                ground_since = now
                            if not catalog_attempted and now-ground_since>=3.0:
                                catalog_attempted=True
                                if not getattr(sm,'request_airport_catalog',lambda:False)():
                                    self._send('airport_catalog_error',
                                        'Consulta MSFS indisponível. Nenhum aeroporto externo será usado.')
                        else:
                            ground_since = None
                        self._send("sample", sample)
                        if reader.soft_missing and now - last_warning >= 15:
                            self._send("warning", "SimVar intermitente: " + ", ".join(sorted(reader.soft_missing)) + "; monitoramento continua")
                            last_warning = now
                    self.stop_event.wait(self.interval)
            except Exception as exc:
                if not self.stop_event.is_set():
                    self._send("warning", f"Conexão interrompida: {exc}. " +
                        ("Tentando reconectar..." if self.reconnect else "Reconexão manual necessária."))
                    if not self.reconnect:
                        self.stop_event.set()
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
