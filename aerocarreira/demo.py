"""Amostras sintéticas, não equivalentes à conexão física com MSFS."""
from time import time
from .domain import AIRPORTS, FlightSample


def demo_samples(destination="SIPE", initial_time=None):
    t = time() if initial_time is None else initial_time
    a, b = AIRPORTS["SBRF"], AIRPORTS[destination]
    def at(seconds, factor, agl, ias, gs, vs, ground):
        return FlightSample(t+seconds,
            a.latitude+(b.latitude-a.latitude)*factor,
            a.longitude+(b.longitude-a.longitude)*factor,
            35+agl, agl, ias, gs, vs, ground)
    return [
        at(0, 0, 0, 0, 0, 0, True),
        at(2, .003, 0, 14, 14, 0, True),
        at(10, .02, 60, 62, 65, 350, False),
        at(30, .30, 1800, 90, 93, 450, False),
        at(55, .62, 2200, 95, 99, 0, False),
        at(85, .92, 900, 70, 72, -470, False),
        at(96, .985, 90, 59, 60, -260, False),
        at(99, .996, 4, 53, 54, -155, False),
        at(100, 1, 0, 50, 48, -110, True),
        at(103, 1, 0, 9, 9, 0, True),
    ]
