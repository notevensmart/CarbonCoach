from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
import re
from app.services.climatiq_api import activity_lookup
from rapidfuzz import process 

load_dotenv(dotenv_path="key.env")  # Load OpenRouter key

# Setup LLM (Claude via OpenRouter)
llm = ChatOpenAI(
    model="deepseek/deepseek-chat-v3-0324:free",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    temperature=0
)

# Prompt template
match_prompt = PromptTemplate(
    input_variables=["user_activity", "choices"],
    template="""
You are a carbon emissions activity matcher.

Your job is to take a **general activity label** and return the **best matching activity name** from a fixed list of formal activity definitions.

---

The label is a short phrase like:
- "bus ride"
- "plastic recycling"
- "beef meal"
- "electricity use"
- "laptop purchase"

---

The formal activity names come from 4 carbon-relevant domains:
- Transport (e.g. "Bus - average")
- Waste (e.g. "Plastic - Recycled - EU")
- Energy (e.g. "Electricity supplied from grid - residual mix")
- Goods/Services (e.g. "Tomatoes canned in juice")

Choose the **closest match** from the list below.  
 Respond with only one exact string from the list.  
 Do not make up your own answers or add extra words.

---

Activity label:
{user_activity}

Available activity names:
{choices}

Return just one best-matching string from the list above.
"""
)


# Build the LangChain Runnable
matcher_chain = match_prompt | llm

def match_activity(user_activity: str):
    candidate_names = list(activity_lookup.keys())
    choices_block = "\n".join(candidate_names)
    
    response = matcher_chain.invoke({
        "user_activity": user_activity,
        "choices": choices_block
    })

    raw = response.content.strip()
    matched_name = re.sub(r"^['\"]|['\"]$", '', raw.lower())
    print(f"🤖 LLM raw response: {raw!r}")
    print(f"🔍 Cleaned match string: {matched_name}")
    # Step 1: Exact match
    if matched_name in activity_lookup:
        activity_id = activity_lookup[matched_name]
        print(f"✅ Exact match: {matched_name} → {activity_id}")
        return activity_id
    
    # Step 2: Fuzzy match
    best_match, score, _ = process.extractOne(matched_name, candidate_names)
    print(f"🧠 Fuzzy matched to: {best_match} (score: {score})")

    if score > 70:
        activity_id = activity_lookup[best_match]
        print(f"✅ Fuzzy fallback match: {best_match} → {activity_id}")
        return activity_id

    print("❌ No confident match found.")
    return None