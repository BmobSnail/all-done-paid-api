"""导出 OpenAPI JSON + 生成 Scalar 静态文档。

用法：
    python -m scripts.export_openapi
    # → 产物：docs/openapi.json + docs/index.html（Scalar）

CI 可在 build 后跑一次，把 docs/ 当 artifact 上传或挂到 GitHub Pages。
"""
from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path

# 默认走 bypass，避免 export 时校验 LLM 凭证
os.environ.setdefault("PAID_API_KEY_PEPPER", "export_openapi_pepper_long_enough_xxx")
os.environ.setdefault("PAID_INTERNAL_BYPASS_ENABLED", "true")

# 若环境未装 pydantic_ai（仅文档生成不需要真实 LLM），打个最小桩
if "pydantic_ai" not in sys.modules:
    try:
        import pydantic_ai  # noqa: F401
    except ModuleNotFoundError:
        stub = types.ModuleType("pydantic_ai")
        stub.Agent = object  # type: ignore[attr-defined]
        sys.modules["pydantic_ai"] = stub
        models = types.ModuleType("pydantic_ai.models")
        openai_mod = types.ModuleType("pydantic_ai.models.openai")
        openai_mod.OpenAIChatModel = object  # type: ignore[attr-defined]
        sys.modules["pydantic_ai.models"] = models
        sys.modules["pydantic_ai.models.openai"] = openai_mod
        providers = types.ModuleType("pydantic_ai.providers")
        provider_openai = types.ModuleType("pydantic_ai.providers.openai")
        provider_openai.OpenAIProvider = object  # type: ignore[attr-defined]
        sys.modules["pydantic_ai.providers"] = providers
        sys.modules["pydantic_ai.providers.openai"] = provider_openai

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOCS.mkdir(parents=True, exist_ok=True)


def _scalar_html(spec_url: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>All-Done Paid API</title>
  <meta name="viewport" content="width=device-width,initial-scale=1" />
</head>
<body>
  <script id="api-reference" data-url="{spec_url}"></script>
  <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>
"""


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from app.main import create_app

    app = create_app()
    spec = app.openapi()
    out_json = DOCS / "openapi.json"
    out_html = DOCS / "index.html"
    out_json.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    out_html.write_text(_scalar_html("./openapi.json"), encoding="utf-8")
    print(f"[export-openapi] paths={len(spec.get('paths', {}))} → {out_json}")
    print(f"[export-openapi] scalar       → {out_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
