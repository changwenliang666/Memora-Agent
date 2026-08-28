from langchain_core.tools import tool,BaseTool
from datetime import datetime
from memora_agent.schema.tools import ToolsDictList,CitySchema

class Tools:
    @tool(
        "get_weather",
        description="根据城市名称获取天气情况,没有输入城市名称则返回无法查询具体的天气情况:请提供城市名称",
        args_schema=CitySchema
    )
    def get_weather(city:str | None = None) -> str:
        if city is None:
            return "无法查询具体的天气情况，请提供城市名称"
        return f"{city}的天气情况：晴天，温度20℃，湿度50%"
    
    @tool("get_current_time",description="获取当前真实时间")
    def get_current_time():
       now = datetime.now()
       weekdays = ["一", "二", "三", "四", "五", "六", "日"]
       return (
           f"当前真实时间是：{now.year}年{now.month}月{now.day}日"
           f"星期{weekdays[now.weekday()]} {now.strftime('%H:%M:%S')}"
        )
    def get_all_tools(self) -> ToolsDictList:
       tools_prompt = ""
       tools_list:list[BaseTool]=[self.get_weather, self.get_current_time]
       for tool in tools_list:
            tools_prompt += f"{tool.name}: {tool.description}\n"
       return {
            "tools_prompt":tools_prompt,
            "tools_list":tools_list
        }
