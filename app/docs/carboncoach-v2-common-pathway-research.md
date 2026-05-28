# CarbonCoach V2 Common Personal Pathway Research

This artifact supports Ticket 11's curated factor metadata overlay. It stays
within the supported V2 categories: `transport`, `energy`, `goods_services`,
and `waste`.

## Sources Reviewed

- EPA, [Sources of Greenhouse Gas Emissions](https://www.epa.gov/ghgemissions/sources-greenhouse-gas-emissions): high-level context for transportation, electricity, residential/commercial energy, industry, agriculture, and waste.
- EPA, [Waste Reduction Model](https://www.epa.gov/waste-reduction-model): material management practices include source reduction, recycling, anaerobic digestion, combustion, composting, and landfilling.
- EPA, [Reducing Waste: What You Can Do](https://www.epa.gov/recycle/reducing-waste-what-you-can-do): household actions include reducing, reusing, recycling, composting food scraps, and keeping materials out of landfill.
- EPA, [Wasted Food Scale](https://www.epa.gov/sustainable-management-food/wasted-food-scale): food waste pathways should distinguish prevention/reuse from composting and disposal.
- EPA, [eGRID](https://www.epa.gov/egrid): electricity emissions factors are tied to generated electricity characteristics and are used for carbon footprints and inventories.
- DOE, [Appliances and Electronics](https://www.energy.gov/energysaver/appliances-and-electronics): household device electricity use is a distinct energy-use family.
- Our World in Data, [Food Choice vs. Eating Local](https://ourworldindata.org/food-choice-vs-eating-local), and Poore & Nemecek 2018, [Science](https://www.science.org/doi/10.1126/science.aaq0216): food product choice, especially beef, can dominate food-related emissions.
- Climatiq, [Search API](https://www.climatiq.io/docs/api-reference/search): factor discovery supports text queries and filters such as category, sector, and unit-related metadata.

## Included Pathway Families

### Waste

Included first because ordinary waste language needs material and method
separated. The overlay covers landfill, recycling, and composting for common
materials: general waste, mixed packaging, plastic, cardboard, paper, glass,
metal, and food scraps.

Boundary: material type never proves disposal method. A phrase such as
`plastic bottles` is not recycling unless the user states recycling, a recycling
bin, or equivalent disposal context. Weight is required; bags and bins are not
converted to mass.

Local factor availability required: estimation is safe only when the raw factor
database or maintained fallback has the same unit type and compatible method.

### Goods Services

Food, drinks, purchases, and services remain under `goods_services`; no top-level
`food` category is introduced. The overlay prioritizes coffee by serving,
coffee by spend, beef by weight, beef burrito/meal by serving, restaurant or
takeaway meal serving, groceries by weight or spend, clothing by item or spend,
and electronics by item or spend.

Boundary: money, item count, and weight are separate calculation shapes. Spend
is not converted into servings or kilograms, and item count is not inferred from
price. Delivery-app context is preserved but delivery travel is excluded unless
distance and mode are separately supplied.

Local factor availability required: generic groceries, clothing, electronics,
and restaurant meals must remain unresolved unless compatible broad factors are
present and validated.

### Transport

The overlay covers common distance-based personal movement: generic car, petrol
car, diesel car, electric car, hybrid car, bus/coach, train/rail/tram/metro,
taxi/rideshare, and flight. Walking/running and cycling are included as explicit
operational-zero boundaries rather than emission-factor pathways.

Boundary: distance is required and is not inferred. Fuel and vehicle class
evidence should rank compatible factors, but unsupported named vehicles must not
create model-level precision without verified metadata.

Local factor availability required: flights and fuel-specific vehicle factors
must pass unit and semantic validation before use.

### Energy

The overlay covers household electricity by kWh, space heater electricity,
air conditioning/cooling, hot water, electric cooking, generic devices, computers
and laptops, and TV/console entertainment devices.

Boundary: kWh is the safe calculation quantity. Power x duration can derive kWh
where the V2 builder already supports it. Vague durations such as `all evening`
or a device name alone do not create kWh unless a maintained assumption rule
exists and is visible.

Local factor availability required: all end uses ultimately retrieve an
electricity-compatible factor by `Energy` unit type; natural gas and unsupported
device defaults remain unresolved until separately maintained.
