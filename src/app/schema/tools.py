from pydantic import BaseModel
from langchain_core.tools import BaseTool

class ToolsDictList(BaseModel):
    tools_prompt:str
    tools_list:list[BaseTool]

class CitySchema(BaseModel):
    city:str | None = None