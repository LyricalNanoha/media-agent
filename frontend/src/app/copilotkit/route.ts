import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { LangGraphHttpAgent } from "@copilotkit/runtime/langgraph";
import { NextRequest } from "next/server";

// 后端Agent地址 - 使用AG-UI协议
// 开发环境: http://localhost:8002/api/copilotkit
// Docker环境: http://127.0.0.1:8000/api/copilotkit
const AGENT_URL = process.env.AGENT_URL || "http://localhost:8002/api/copilotkit";

// 使用EmptyAdapter因为我们的Agent在后端
const serviceAdapter = new ExperimentalEmptyAdapter();

// 创建CopilotRuntime，使用LangGraphHttpAgent连接自托管的FastAPI
const runtime = new CopilotRuntime({
  agents: {
    media_agent: new LangGraphHttpAgent({
      url: AGENT_URL,
    }),
  },
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter,
    endpoint: "/copilotkit",  // 中间层端点（不带 /api）
  });

  return handleRequest(req);
};

