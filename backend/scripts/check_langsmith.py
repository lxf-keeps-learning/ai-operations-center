"""快速验证 LangSmith 是否连通。"""
from app.config.settings import settings
from app.observability.langsmith_tracing import _get_client

settings.langsmith_tracing = True
_get_client.cache_clear()

client = _get_client()
if client is None:
    print("❌ LangSmith 客户端初始化失败，请检查 LANGSMITH_API_KEY 是否正确")
else:
    try:
        projects = list(client.list_projects(limit=3))
        print(f"✅ LangSmith 连接成功！项目列表（前 3 个）:")
        for p in projects:
            print(f"   - {p.name}")
        print(f"\n当前配置项目: {settings.langsmith_project}")
    except Exception as e:
        print(f"❌ LangSmith API 调用失败: {e}")
