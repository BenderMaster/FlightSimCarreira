"""MSFS 2020 contract turnaround: verified gate/ramp, not touchdown, pays.

The gate never assumes that being on the ground means parked. Unknown SimVars
are unknown, not False. Touchdown and contract settlement remain distinct
events; the original SQLite flight finalizer owns the single atomic payment.
"""
from __future__ import annotations

from dataclasses import asdict
from math import isfinite
from .domain import distance_nm


def parking_status(sample, *, shutdown=False):
    """Return (eligible, user-facing reason). No shortcuts on missing sensors."""
    if sample is None or not sample.on_ground:
        return False, 'A aeronave precisa estar no solo.'
    runway=getattr(sample,'on_any_runway',None)
    if runway is True:
        return False, 'A aeronave está na pista. Taxie até um portão ou estacionamento.'
    if runway is None:
        return False, 'O SimConnect não retornou ON ANY RUNWAY. Sem confirmação de saída da pista, o aceite permanece bloqueado.'
    spot=(getattr(sample,'atc_on_parking_spot',None) is True or
          getattr(sample,'plane_in_parking_state',None) is True)
    if not spot:
        return False, 'Posicione-se no portão, pátio ou estacionamento identificado pelo MSFS.'
    velocity=getattr(sample,'groundspeed_kt',None)
    if (getattr(sample,'groundspeed_estimated',True) or
            type(velocity) not in (float,int) or not isfinite(velocity) or velocity>1.5 or velocity<0):
        return False, 'Imobilize a aeronave; a velocidade real de solo deve ser inferior a 1,5 kt.'
    if getattr(sample,'parking_brake_set',None) is not True:
        return False, 'Acione o freio de estacionamento.'
    if shutdown and getattr(sample,'engine_running',None) is not False:
        return False, 'Desligue todos os motores e aguarde a confirmação do SimConnect.'
    return True, 'Estacionamento confirmado.' if not shutdown else 'Aguardando estabilização do pós-voo.'


class TurnaroundGate:
    """Continuous 6-second shutdown at destination after a verified landing."""
    def __init__(self, *, hold_s=6.0):
        self.hold_s=hold_s
        self.pending=None
        self.since=None
        self.last=None
        self.reason=None

    def begin(self, event, sample, mission_id):
        if self.pending is not None:
            raise ValueError('Já existe pouso aguardando desembarque.')
        if not isinstance(event,dict) or event.get('type')!='landing' or not mission_id:
            raise ValueError('Conclusão exige pouso e contrato verificados.')
        self.pending={'event':dict(event),'mission_id':str(mission_id),
                      'aircraft_title':sample.aircraft_title}
        self.since=None
        self.last=sample.timestamp
        self.reason='Pouso confirmado. Táxi até estacionamento, freio e motores desligados.'

    def observe(self,sample,mission_id):
        if not self.pending:
            return False
        if mission_id!=self.pending['mission_id']:
            self.since=None
            self.reason='Contrato foi alterado; crédito bloqueado.'
            return False
        if sample.aircraft_title!=self.pending['aircraft_title']:
            self.since=None
            self.reason='Aeronave alterada durante o desembarque; crédito bloqueado.'
            return False
        if self.last is not None and (sample.timestamp<=self.last or sample.timestamp-self.last>4):
            self.since=None
        self.last=sample.timestamp
        ok,reason=parking_status(sample,shutdown=True)
        if not ok:
            self.since=None
            self.reason=reason
            return False
        if self.since is None:
            self.since=sample.timestamp
        elapsed=sample.timestamp-self.since
        self.reason='Encerrando operação: %.0f / %.0f segundos.'%(min(elapsed,self.hold_s),self.hold_s)
        return elapsed>=self.hold_s

    def snapshot(self):
        return {'pending':self.pending,'since':self.since,'last':self.last,'reason':self.reason}

    @classmethod
    def restore(cls,raw):
        result=cls()
        if not isinstance(raw,dict):return result
        p=raw.get('pending')
        if (isinstance(p,dict) and isinstance(p.get('event'),dict) and
                p['event'].get('type')=='landing' and
                isinstance(p.get('mission_id'),str)):
            result.pending={'event':dict(p['event']),
                            'mission_id':p['mission_id'],
                            'aircraft_title':p.get('aircraft_title')}
            result.reason=str(raw.get('reason') or '')[:200]
            # Never restore elapsed hold across restarts/connection drops.
            result.since=None
            result.last=None
        return result
