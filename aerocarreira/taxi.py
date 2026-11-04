"""Classificação conservadora de táxi, corrida de decolagem e frenagem de pouso.

Prioriza ON ANY RUNWAY, mas esse sinal pode estar ausente em aeroportos
customizados. Nunca confundir velocidade estimada por IAS com GS medida.
Não movimenta a aeronave e não usa componentes dependentes de UI.
"""
from __future__ import annotations
from math import isfinite


def heading_delta(a, b):
    if a is None or b is None:
        return None
    try:
        a=float(a); b=float(b)
        if not isfinite(a) or not isfinite(b):return None
    except (ValueError, TypeError, OverflowError):
        return None
    return abs((b-a+180)%360-180)


def sample_heading(s):
    return s.heading_true_deg if s.heading_true_deg is not None else s.heading_magnetic_deg


class DepartureTaxi:
    """Anota episódios; só calcula penalidades quando a decolagem é confirmada."""
    def __init__(self):
        self.start=None
        self.start_heading=None
        self.start_speed=0.0
        self.peak_speed=0.0
        self.max_turn=0.0
        self.speed_dropped=False
        self.last_speed=0.0
        self.reported=False
        self.suspects=[]

    def _reset_segment(self):
        self.start=None;self.start_heading=None;self.start_speed=0.0
        self.peak_speed=0.0;self.max_turn=0.0;self.speed_dropped=False
        self.last_speed=0.0;self.reported=False

    def observe(self, s):
        if not s.on_ground or s.groundspeed_estimated or s.on_any_runway is True:
            self._reset_segment();return
        fast=25 < s.groundspeed_kt < 75 and s.ias_kt < 45
        if not fast:
            # Velocidade caiu antes de entrar na pista: era táxi rápido,
            # não uma corrida de decolagem que acelerou continuamente.
            if (self.reported and self.suspects
                    and s.groundspeed_kt < self.peak_speed-6):
                self.suspects[-1]['speed_drop']=True
            self._reset_segment();return
        current_heading=sample_heading(s)
        if self.start is None:
            self.start=s.timestamp
            self.start_heading=current_heading
            self.start_speed=s.groundspeed_kt
            self.peak_speed=s.groundspeed_kt
            self.last_speed=s.groundspeed_kt
        else:
            d=heading_delta(self.start_heading,current_heading)
            if d is not None:self.max_turn=max(self.max_turn,d)
            self.speed_dropped |= s.groundspeed_kt < self.last_speed-6
            self.last_speed=s.groundspeed_kt
            self.peak_speed=max(self.peak_speed,s.groundspeed_kt)
        if not self.reported and s.timestamp-self.start>=8:
            self.suspects.append(dict(at=s.timestamp,known_taxi=s.on_any_runway is False,
                  initial_heading=self.start_heading,max_turn=self.max_turn,
                  speed_drop=self.speed_dropped,peak_speed=self.peak_speed,
                  initial_speed=self.start_speed))
            self.reported=True

    def takeoff(self, s):
        violations=0
        for item in self.suspects:
            age=s.timestamp-item['at']
            diff=heading_delta(item.get('initial_heading'),sample_heading(s))
            mostly_straight=diff is None or diff <= 12
            runway_accel=(0<=age<=50 and mostly_straight
                          and item.get('max_turn',0)<=12
                          and not item.get('speed_drop',False)
                          and s.groundspeed_kt>=max(45,item.get('peak_speed',25)+10))
            # A bandeira explícita "fora da pista" prevalece para episódios
            # antigos de táxi. Em cenários sem flag, acelerou reto e decolou:
            # classificar como corrida de decolagem, não infração.
            # Aeroportos de terceiros podem retornar False mesmo na
            # cabeceira: uma aceleração reta até decolar tem prioridade.
            # Episódios com curva ou desaceleração continuam puníveis.
            if not runway_accel:
                violations+=1
        self._reset_segment();self.suspects=[]
        return min(2,violations)

    def snapshot(self):
        return dict(start=self.start,start_heading=self.start_heading,
            start_speed=self.start_speed,peak_speed=self.peak_speed,
            max_turn=self.max_turn,speed_dropped=self.speed_dropped,
            last_speed=self.last_speed,reported=self.reported,
            suspects=self.suspects)

    @classmethod
    def from_snapshot(cls,data):
        ob=cls()
        if isinstance(data,dict):
            for key in ob.snapshot():
                if key in data:setattr(ob,key,data[key])
        return ob


class PostLandingTaxi:
    """Só pontua táxi DEPOIS da frenagem: sem cobrança durante rollout."""
    def __init__(self,flight_key=None,touchdown_at=None,heading=None):
        self.flight_key=flight_key
        self.touchdown_at=touchdown_at
        self.start_heading=heading
        self.phase='rollout' if flight_key else 'inactive'
        self.fast_since=None
        self.penalty_marked=False
        self.last_timestamp=None
        self.seen_runway_true=False

    @classmethod
    def begin(cls,start,s):
        key='takeoff:{:.6f}:{:.7f}:{:.7f}'.format(
            float(start['timestamp']),float(start['lat']),float(start['lon']))
        monitor=cls(key,s.timestamp,sample_heading(s))
        monitor.seen_runway_true=s.on_any_runway is True
        return monitor

    def observe(self,s):
        """Retorna flight_key uma única vez se houver infração após o pouso."""
        if self.phase in ('inactive','done') or self.penalty_marked:return None
        if self.last_timestamp is not None and s.timestamp<=self.last_timestamp:return None
        self.last_timestamp=s.timestamp
        if not s.on_ground or s.timestamp-self.touchdown_at>1800:
            self.phase='done';return None
        if s.groundspeed_estimated:return None
        if s.on_any_runway is True:self.seen_runway_true=True
        turn=heading_delta(self.start_heading,sample_heading(s))
        if self.phase=='rollout':
            # Frenagem continua isenta até desacelerar, sair da pista com
            # velocidade moderada, ou efetuar curva própria do taxiamento.
            if s.groundspeed_kt<=10 or (
                self.seen_runway_true and s.on_any_runway is False
                and s.groundspeed_kt<=28
            ) or (turn is not None and turn>=30 and s.groundspeed_kt<=32):
                self.phase='taxi'
            else:
                return None
        if self.phase=='taxi':
            if s.on_any_runway is True or s.engine_running is False:
                self.fast_since=None;return None
            if s.groundspeed_kt>25:
                if self.fast_since is None:self.fast_since=s.timestamp
                if s.timestamp-self.fast_since>=8:
                    self.penalty_marked=True;self.phase='done'
                    return self.flight_key
            else:self.fast_since=None
        return None

    def snapshot(self):
        return dict(flight_key=self.flight_key,touchdown_at=self.touchdown_at,
          start_heading=self.start_heading,phase=self.phase,
          fast_since=self.fast_since,penalty_marked=self.penalty_marked,
          last_timestamp=self.last_timestamp,
          seen_runway_true=self.seen_runway_true)

    @classmethod
    def from_snapshot(cls,raw):
        if not isinstance(raw,dict):return cls()
        ob=cls(raw.get('flight_key'),raw.get('touchdown_at'),raw.get('start_heading'))
        for key in ('phase','fast_since','penalty_marked','last_timestamp','seen_runway_true'):
            if key in raw:setattr(ob,key,raw[key])
        return ob
