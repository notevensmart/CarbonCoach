from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from dotenv import load_dotenv
import os
bool = False
load_dotenv(dotenv_path="key.env")
print("✅ Loaded key:", os.getenv("OPENROUTER_API_KEY")[:8] + "...")
# Step 1: Setup LLM

llm = ChatOpenAI(
    model="anthropic/claude-3-haiku",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    temperature=0
)  # or gpt-3.5-turbo

# Step 2: Define prompt
prompt = PromptTemplate(
    input_variables=["journal_entry"],
    template="""
You are an assistant that extracts high-level daily activity categories from text.

Given this journal entry:
"{journal_entry}"

Extract and return a list of activity labels that map to carbon-relevant categories like transport, food, waste, goods, or energy use. Example outputs: 'Travel by car', 'Beef meal', 'Plastic waste disposal'.

Only return a Python list of string labels.
"""
)

# Step 3: LangChain LLMChain basically piping the prompt into the llm
classify_chain = prompt | llm

# Step 4: Wrapper function
def classify_activities(journal_entry: str):
    response = classify_chain.invoke({"journal_entry":journal_entry})
    try:
        # Evaluate the string into a real Python list
        list_str =eval(response.content)
        bool = True
        return list_str
        
    except:
        return ["[Unparseable output]"]

result = classify_activities("Today I drove to work by car for 5km, had a salad for lunch, and recycled some plastic bottles.")
print("Extracted activity labels:", result)