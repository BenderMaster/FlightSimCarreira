import unittest
from aerocarreira.domain import AIRPORTS, MISSIONS, Career, FlightTracker, FlightSample, Phase, distance_nm
from aerocarreira.demo import demo_samples


class DomainTests(unittest.TestCase):
    def test_airport_distance(self):
        a = AIRPORTS['SBRF']; b = AIRPORTS['SIPE']
        self.assertAlmostEqual(distance_nm(a.latitude,a.longitude,a.latitude,a.longitude),0.0)
        self.assertTrue(25 < distance_nm(a.latitude,a.longitude,b.latitude,b.longitude) < 33)

    def test_demo_flight_starts_lands(self):
        tracker=FlightTracker()
        events=[]
        for sample in demo_samples(initial_time=1000):
            events.extend(tracker.update(sample))
        self.assertEqual([e['type'] for e in events], ['takeoff','landing'])
        self.assertEqual(tracker.phase, Phase.LANDED)
        self.assertEqual(events[-1]['touchdown_fpm_est'], -155)

    def test_mission_reward_only_correct_destination(self):
        c=Career()
        samples=demo_samples(initial_time=1000)
        c.accept(MISSIONS[0],samples[0])
        tr=FlightTracker()
        for s in samples:
            ev=tr.update(s)
            c.evaluate([e for e in ev if e['type']=='takeoff'])
            result=c.evaluate([e for e in ev if e['type']=='landing'])
        self.assertEqual(result['reward'],850)
        self.assertEqual(c.balance,5850)
        self.assertIsNone(c.mission)

    def test_wrong_destination_no_reward(self):
        c=Career()
        c.accept(MISSIONS[1],demo_samples(initial_time=10)[0])  # SBJP
        tr=FlightTracker()
        for s in demo_samples(initial_time=10):
            c.evaluate(tr.update(s))
        self.assertEqual(c.balance,5000)
        self.assertIsNotNone(c.mission)

    def test_wrong_departure_no_reward(self):
        c=Career()
        c.accept(MISSIONS[0])
        b=AIRPORTS['SBJP']
        c.evaluate([{'type':'takeoff','lat':b.latitude,'lon':b.longitude,'timestamp':0}])
        b=AIRPORTS['SIPE']
        self.assertIsNone(c.evaluate([{'type':'landing','lat':b.latitude,'lon':b.longitude,'timestamp':1}]))
        self.assertEqual(c.balance,5000)

    def test_bounce_does_not_double_land(self):
        seq=demo_samples(initial_time=1000)
        tr=FlightTracker()
        events=[]
        for s in seq[:-2]: events+=tr.update(s)
        near=seq[-2]
        # toque, bate e volta ao ar em menos de 2s
        events+=tr.update(near)
        in_air=FlightSample(near.timestamp+0.5,near.latitude,near.longitude,40,5,48,45,-100,False)
        events+=tr.update(in_air)
        events+=tr.update(FlightSample(near.timestamp+1,near.latitude,near.longitude,35,0,30,20,-125,True))
        events+=tr.update(FlightSample(near.timestamp+4,near.latitude,near.longitude,35,0,8,8,0,True))
        self.assertEqual([x['type'] for x in events].count('landing'),1)

    def test_time_backwards_ignored(self):
        tr=FlightTracker()
        s=demo_samples(initial_time=100)[0]
        tr.update(s)
        self.assertEqual(tr.update(s),[])
        self.assertEqual(tr.phase,Phase.GROUND)

    def test_stall_warning_only_on_edge(self):
        tr=FlightTracker()
        seq=demo_samples(initial_time=10)
        for s in seq[:3]: tr.update(s)
        a=seq[3]
        from dataclasses import replace
        tr.update(replace(a,stall_warning=True))
        tr.update(replace(seq[4],stall_warning=True))
        self.assertEqual(tr.stalls,1)

    def test_accept_when_far_disallowed(self):
        c=Career()
        b=AIRPORTS['SBJP']
        from dataclasses import replace
        s=replace(demo_samples(initial_time=100)[0], latitude=b.latitude,longitude=b.longitude)
        with self.assertRaises(ValueError): c.accept(MISSIONS[0],s)
