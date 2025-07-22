# 🧭 CarbonCoach (v0.1)

**CarbonCoach** is an AI-powered assistant that estimates carbon emissions based on natural language journal entries. It uses language models to classify, match, and query emissions data using the Climatiq API.

---

## 🌱 What It Does

You can write something like:

> “I took a 10 km bus ride to work, had a vegetarian meal for lunch and took a shower at night."

And CarbonCoach will:

1. **Extract** carbon-relevant activities from the journal.
2. **Match** each activity to an official emissions category.
3. **Select** default parameters (e.g. distance, energy).
4. **Query** Climatiq’s API to estimate emissions.
5. **Return** emissions per activity and a total footprint.

---

## ⚙️ Current Features (v0.1)

✅ LLM-based journal activity classification  
✅ Activity matching with exact + fuzzy fallback  
✅ Emissions estimation via Climatiq API  
✅ Default parameters based on category (transport, energy, waste, goods)  
✅ Sum of total emissions printed to terminal  

---

## 🧪 Example Output

```bash
🧠 LLM-classified labels: [('bus ride', 'transport'), ('vegetarian meals', 'goods_services'), ('shower', 'energy')]

✅ Exact match: bus → passenger_vehicle-vehicle_type_bus-...
🌱 Emission estimate: 0.414 kg

✅ Exact match: vegetables (fresh) → consumer_goods-type_vegetables_fresh


✅ Exact match: electricity - use: sanitary hot water → ...
🌱 Emission estimate: 0.257 kg

🧾 Total CO2 emissions: 0.671 kg CO2e



