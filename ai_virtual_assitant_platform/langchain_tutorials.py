import os
from langchain_openai import ChatOpenAI

os.environ["OPENAI_API_KEY"] = "open-api-key"

model = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7
)

response = model.invoke("Why do parrots talk?")
print(response.content)
