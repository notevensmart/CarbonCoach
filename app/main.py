from app.services.llm_matcher import match_activity

activity = "Bus ride"
activity_id = match_activity(activity)

print("🔍 Final matched activity_id:", activity_id)

