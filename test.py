from app.services.climatiq_api import extract_unit_info , search_activity_ids
import asyncio
activity_id = "education-type_other_educational_services_provided_by_governments"
async def main():
    unit_type,unit = await extract_unit_info(activity_id)
    print(f"✅ Unit type: {unit_type}")
async def test():
    results = await search_activity_ids("treadmill machine")
    for r in results:
        print(f"{r['name']} → {r['activity_id']} | {r['unit_type']}")

asyncio.run(test())

#asyncio.run(main())

#u,v =extract_unit_info2("electricity-supply_grid-source_residual_mix")
#x,y = extract_unit_info2("education-type_other_educational_services_provided_by_governments")
