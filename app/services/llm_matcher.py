from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
from app.services.climatiq_api import activity_lookup
import ast

load_dotenv(dotenv_path="key.env")  # Load OpenRouter key

# Setup LLM (Claude via OpenRouter)
llm = ChatOpenAI(
    model="deepseek/deepseek-chat-v3-0324:free",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0
)

# Prompt template
match_prompt = PromptTemplate(
    input_variables=["labels","choices"],
    template="""
You are a carbon activity matcher.

You will receive a list of activity labels and a list of formal activity names.

For each label, return the single best-matching formal activity name from the list.

Respond ONLY with a Python dictionary mapping each label to its best match.

- Do NOT include explanations, comments, or any extra text.
- Do NOT wrap your response in markdown or code formatting.
- Do NOT output ```python or ```.


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

Activity labels:
{labels}

Available activity names:
{choices}


Respond ONLY with the dictionary.
"""
)


# Build the LangChain Runnable
matcher_chain = match_prompt | llm

def batch_match_activities(labels: list[str]):
    candidate_names = list(activity_lookup.keys())
    choices_block = "\n".join(candidate_names)
    labels_block = "\n".join(labels)

    response = matcher_chain.invoke({
        "labels": labels_block,
        "choices": choices_block
    })

    raw = response.content.strip()
    print("🤖 Raw LLM response:", repr(raw))

    try:
        mapping = ast.literal_eval(raw)
        return mapping
    except Exception as e:
        print("⚠️ Failed to parse matcher output:", e)
        return {}