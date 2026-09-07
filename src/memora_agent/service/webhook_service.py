import httpx2
from memora_agent.core.config import config

class WebhookService:
    @staticmethod
    def send_knowledge_base_build_success(filename:str):
        print(f"文件名：{filename}")
        response = httpx2.post(config.feishu.webhook_url,json={"msg_type":"text","content":{"text":f"文档：{filename}已经入库；操作人：常文亮"}})
        if response.status_code == 200:
            print("✅ 飞书 webhook 发送成功")
        else:
            print("❌ 飞书 webhook 发送失败")

