from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from dotenv import load_dotenv
import os
bool = False
# Step 1: Setup LLM

llm = ChatOpenAI(
    model="anthropic/claude-3-haiku",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0
)  # or gpt-3.5-turbo

# Step 2: Define prompt
prompt = PromptTemplate(
    input_variables=["journal_entry"],
    template="""
You are a carbon activity classifier.

Given a personal journal entry, extract a list of activity labels along with their category. Each item must be a tuple of the form (label, category).

Categories must be one of:
- "transport"
- "waste"
- "energy"
- "goods_services"

Journal entry:
"{journal_entry}"

Respond with ONLY a valid Python list of (label, category) tuples.
No explanations. No markdown. No code blocks. No extra text.

Example:
[("bus ride", "transport"), ("recycle plastic", "waste")]
"""
)


# Step 3: LangChain LLMChain basically piping the prompt into the llm
classify_chain = prompt | llm

# Step 4: Wrapper function
def classify_activities(journal_entry: str) -> list[tuple[str, str]]:
    response = classify_chain.invoke({"journal_entry": journal_entry})
    ##print("LLM response:", repr(response.content))
    try:
        activity_pairs = eval(response.content.strip())
        return activity_pairs
    except Exception:
        return [("[Unparseable output]", "unknown")]
