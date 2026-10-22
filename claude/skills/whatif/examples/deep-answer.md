# A deep answer

Deep mode only. One complete worked answer in movements, with the claims ledger
that licensed its named things printed after it.

Read it before drafting. `longform.md` explains what it is doing; this is the
thing itself, and matching its rhythm is the point. Note in particular what the
breaks are doing — each movement answers a different question the scenario
raises, and none of them could be reordered without the argument falling over.

The question is not in the What If? archive and no text here is copied from it.

---

<example>

> What if a hospital had to run entirely on one lightning strike a day?
> — Wren

About ten minutes.

Then the lights go out, and they stay out for twenty-three hours and fifty
minutes, and the hospital is a building.

Getting the strike is the part we have to wave through, so let us wave it
through: once a day, on schedule, straight down a conductor of your choosing.
That is a large thing to waive. The most lightning-struck square kilometre on
Earth is at the southern end of Lake Maracaibo in Venezuela, which takes about
233 flashes per square kilometre per year, and a hospital roof is about a
hundredth of a square kilometre.[1] So even there, standing in the lightning
capital of the world, the roof gets hit twice a year. A strike a day is roughly
a hundred and sixty Maracaibos stacked on one building.

Fine. It arrives. Everything after this obeys physics.

A hospital is a surprisingly hungry building. The 2018 US commercial buildings
survey puts an inpatient hospital at about 265,000 square feet using about 193
thousand Btu per square foot per year, all fuels counted, which works out at 1.7
megawatts running continuously, day and night, forever.[2] Checking that a
second way: about 5.5 kilowatts per bed across three hundred beds gives 1.6
megawatts. Close enough to believe.

That is 147 gigajoules a day.

A lightning flash carries something like one gigajoule.

[drawing: a stick figure in scrubs on the hospital roof at three in the morning,
holding a stopwatch and looking up. A hand-lettered sign wired to the lightning
rod reads NEXT SERVICE 24 HRS]

I should be honest about that number, because it is the one the whole answer
turns on and nobody can pin it down. What is measured is the voltage: the
National Severe Storms Laboratory puts a flash somewhere between 100 million and
a billion volts.[3] What is not measured, at least not to any precision worth
quoting, is how much charge actually moves. Multiply plausible ends together and
a flash lands anywhere from a tenth of a gigajoule to twenty.

So the honest answer is a range. At the low end you get sixty seconds of
hospital. At the high end, an hour and a half. The middle, and the number I will
use from here, is about ten minutes.[4]

Ten minutes is one operation, if nothing goes wrong.

[break]

The energy is not the problem.

This is the part that surprised me, and it is worth sitting with, because a
gigajoule is genuinely not very much. Four hundred litres of petrol. A fuel
tanker with the tap left open for about a minute. Nobody would build a power
scheme around a gigajoule a day and expect to run anything larger than a
supermarket, and nobody would call the supermarket dangerous.

What makes lightning lightning is not how much energy it carries but how fast
it lets go.

A flash is over in a few thousandths of a second. Push a gigajoule through a
millisecond and you get a terawatt — and the world's entire electrical
generating fleet, every station on every continent, averages about three and a
half terawatts.[5] For that millisecond, the thing hitting your roof is
delivering something like a third of the output of human civilisation, into a
copper strap, in a hospital car park.

Nothing you can build takes delivery of that.

The failure is not that the equipment gets damaged, although it does. What
happens is that a conductor asked to carry a terawatt for a millisecond stops
being a conductor almost immediately and becomes a short length of expanding
copper vapour. Lightning heats the air in its own channel to somewhere between
18,000 and 60,000 degrees Fahrenheit.[6] It does that to air, which it does not
even want to go through. Your cable is a better route, which is precisely why it
gets the worse end of the deal.

There is a further indignity waiting underneath that one, which is that most of
the gigajoule was never going to be yours in the first place. The channel spends
it on heat, on light, and on shoving several tonnes of air sideways hard enough
to be audible eight miles away. Thunder is not a side effect of the energy
transfer. Thunder is a large fraction of where the energy went.

You are not tapping a supply. You are standing under an explosion with a bucket.

[drawing: an engineer standing in the rain holding a plug in one hand and
gesturing upward with the other, trying to get the bolt to line up with the
socket. The bolt has already gone somewhere else]

[break]

Suppose you solved that.

You have not, and nobody has, but the next problem is more interesting than the
one you are stuck on, so grant yourself a perfect catcher and see what it hands
you. It hands you a gigajoule, in a millisecond, once a day, and now you have to
keep it until somebody needs a ventilator at four in the afternoon.

You cannot put it in a battery. Not because a battery is too small — a lithium
cell holds about 250 watt-hours per kilogram, so a gigajoule is a bit over a
tonne of them, which is a large delivery but not an absurd one. You cannot use a
battery because nothing electrochemical charges in a millisecond. Chemistry has
a speed limit and it is nowhere near that.

What charges in a millisecond is a capacitor. Supercapacitors run at something
like 10 watt-hours per kilogram, a twenty-fifth of the lithium cell, and a
gigajoule of them comes to about 28 tonnes.[7]

Twenty-eight tonnes. In the basement. To hold ten minutes.

[drawing: a cutaway of the hospital basement, entirely occupied by a single
capacitor the size of the building. A small door in the side is labelled MRI,
RELOCATED]

And here is what the tidy version of all this has been quietly ignoring, which
is that a hospital does not need power on average. It needs power at the moment
it needs it, which is not negotiable and not schedulable, and the whole design
problem is margin rather than supply.

One strike a day has no margin at all. Ten minutes exactly, and nothing over. A
late strike is a dead patient. A weak strike — and we established that flash
energy varies by a factor of two hundred between the ends of its range — is a
dead patient. A strike that lands forty metres away in the car park, which is
what lightning mostly does, is a dead patient and a hole in the tarmac.

Margin is not a luxury the building bolted on afterwards. Margin is the whole
building. Everything a hospital does that looks like paranoia — the second
supply, the second tank, the weekly test nobody enjoys — exists because the
failure mode is not "the lights flicker" but "the theatre goes dark with someone
open on the table".

[break]

Real hospitals solved this, and the solution is boring in the specific way that
good engineering is boring.

The relevant standard is NFPA 110, which classifies emergency power systems by
how long they must run and how fast they must take over. A hospital is Level 1 —
the category defined by the failure of the system being able to kill someone —
and it is typically specified Class 96, Type 10.[8] Class 96 means the standby
supply carries the building for ninety-six hours without resupply. Type 10 means
the transfer completes within ten seconds of the mains failing.

Ten seconds, ninety-six hours. Those two numbers are the entire argument, and
between them they describe a machine that is the exact opposite of a lightning
strike: it is slow, it is patient, and its whole value is that you know in
advance when it will start.

The ten seconds is not the generator being sluggish, incidentally. It is a
diesel engine being asked to go from cold and stationary to carrying a megawatt,
which is an unreasonable thing to ask of an engine and is why the standard says
ten rather than one.

A Class 96 tank at 1.7 megawatts holds about 590 gigajoules, which is roughly
16,000 litres of diesel.[9] Sitting in that tank, in a quiet room, doing nothing
at all, is the energy of about six hundred lightning strikes.

[drawing: a fuel lorry reversing up to the hospital loading bay. Drawn stacked
inside its tank, neatly, like cordwood, are 588 small lightning bolts]

So the tank in the basement already is the lightning. Nearly six hundred strikes
of it, at 12,000 watt-hours per kilogram instead of ten, arriving on a schedule
somebody negotiated, in a container that does not mind waiting. Diesel is not
competing with lightning on power. It wins on every axis lightning was never in
the running for: density, patience, and knowing in advance when it will show up.

Lightning is not a power source that happens to be inconvenient. It is a
discharge — the sky equalising a charge imbalance by the shortest available
route, with no more intention behind it than water has when it finds the low
corner of a floor. The energy was never being delivered anywhere. It was being
got rid of.

Which is why the entire industry that exists around lightning and buildings is
about persuading it to go somewhere else, in a straight line, at speed, without
touching anything on the way.

[drawing: a stick figure asleep in a hospital bed. Outside the window a storm is
happening. Inside, nothing whatsoever is different]

Nobody is trying to catch it. They are trying to be rude to it.

[1] 233 flashes per square kilometre per year, from the sixteen years of data the Lightning Imaging Sensor collected aboard TRMM. The runners-up are almost all in the Congo basin, which does not get to call itself anything.

[2] The survey reports this as "MBtu per square foot", where M is the Roman thousand and not the metric million, a convention the energy industry has declined to abandon for about a century.

[3] They publish the voltage and decline to publish a current, which I take as the honest position of people who have tried to measure it.

[4] Two significant figures would be generous. One is closer to what I have.

[5] Annual world electricity generation divided by the number of seconds in a year. It is an average, so it flatters lightning slightly: at four in the afternoon the fleet is doing rather more than that.

[6] Fahrenheit because that is the unit it was published in, and converting a range that wide would imply a precision nobody claimed.

[7] Five to ten watt-hours per kilogram is the honest band for a commercial supercapacitor. I have used the optimistic end, which is the direction that makes the answer look better and still does not save it.

[8] Class and Type are separate axes and they multiply, which is how you end up specifying a machine by two numbers that sound like the same number.

[9] Diesel at 36 megajoules per litre. The tank is usually two tanks, because a single point of failure in the thing that exists to remove single points of failure is the sort of joke standards committees do not make twice.

</example>

---

## The ledger that licensed this

Written to `claims.tsv` in the scratch directory by the parent, from the
workflow's verification rows. Every name in the answer above appears here as
VERIFIED. Note what the UNVERIFIED rows did: they did not become hedged
sentences, they became nothing. The answer does not mention them.

```
status	name	url	title	note
VERIFIED	Lake Maracaibo	https://www.nasa.gov/missions/trmm/earths-new-lightning-capital-revealed/	Earth's New Lightning Capital Revealed	233 flashes/km2/yr; southern end of the lake
VERIFIED	Venezuela	https://www.nasa.gov/missions/trmm/earths-new-lightning-capital-revealed/	Earth's New Lightning Capital Revealed	same page; where the lake is
VERIFIED	Bulletin of the American Meteorological Society	http://journals.ametsoc.org/doi/abs/10.1175/BAMS-D-14-00193.1	Where are the Lightning Hotspots on Earth?	linked from the NASA page above
VERIFIED	Lightning Imaging Sensor	https://www.nasa.gov/missions/trmm/earths-new-lightning-capital-revealed/	Earth's New Lightning Capital Revealed	16 years of data, aboard TRMM
VERIFIED	TRMM	https://www.nasa.gov/missions/trmm/earths-new-lightning-capital-revealed/	Earth's New Lightning Capital Revealed	Tropical Rainfall Measuring Mission
VERIFIED	Congo	https://www.nasa.gov/missions/trmm/earths-new-lightning-capital-revealed/	Earth's New Lightning Capital Revealed	283 of the top 500 hotspots are in Africa
VERIFIED	National Severe Storms Laboratory	https://www.nssl.noaa.gov/education/svrwx101/lightning/faq/	Severe Weather 101: Lightning FAQ	100 million to 1 billion volts; air heated 18,000-60,000 F
VERIFIED	2018 US commercial buildings survey	https://www.eia.gov/consumption/commercial/pba/health-care.php	CBECS: Health Care Buildings	hospitals average 264,800 sq ft at 193.3 thousand Btu/sq ft
VERIFIED	NFPA 110	https://www.cummins.com/sites/default/files/2019-03/PowerHour_NFPA110.pdf	NFPA 110 Type 10 Requirements	Level 1 / Class 96 / Type 10; the standard itself is paywalled, so this rests on B-tier
VERIFIED	Class 96	https://www.cummins.com/sites/default/files/2019-03/PowerHour_NFPA110.pdf	NFPA 110 Type 10 Requirements	96 hours of on-site fuel
VERIFIED	Type 10	https://www.cummins.com/sites/default/files/2019-03/PowerHour_NFPA110.pdf	NFPA 110 Type 10 Requirements	transfer within 10 seconds
VERIFIED	Level 1	https://www.cummins.com/sites/default/files/2019-03/PowerHour_NFPA110.pdf	NFPA 110 Type 10 Requirements	failure of the system risks loss of life
UNVERIFIED	charge transferred per flash			no primary figure found; carried as own estimate and said so on the page
UNVERIFIED	supercapacitor 10 Wh/kg			engineering range is 5-10; carried as own estimate
UNVERIFIED	world generation 3.4 TW			own arithmetic from annual generation; basis stated in the footnote
```

Three things to notice.

The NFPA row is VERIFIED against a manufacturer's training deck rather than the
standard, because the standard is paywalled. The note says so. That is the right
outcome: the claim is real, the evidence is B-tier, and the reader is not told
otherwise.

The charge-per-flash row is the load-bearing quantity in the whole answer and it
is UNVERIFIED. That did not kill the answer — it became the answer's most honest
paragraph, and the two-hundred-fold range is more interesting than a confident
single figure would have been.

Nothing named in the prose is missing from this table. `check.py --claims` is
what proves it, and it reads the footnotes too.
