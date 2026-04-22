"""LLM 适配层：业务代码不应直接 import openai / pydantic_ai，统一经由本子包访问。

子模块：
- provider.py    Provider 抽象（供未来切换 LiteLLM Proxy 等）
- siliconflow.py Provider 实现（OpenAI 兼容协议）
- client.py      多 Key 池 + 模型档位选择
- result_types.py  MeihuaInterpret 等强类型
- agents.py      Pydantic AI Agent 工厂 + 流式封装
- observability.py  Logfire 接入（可关停）
- retry.py       tenacity 重试 / Semaphore 并发 / 熔断 / fallback
"""
