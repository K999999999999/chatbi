import "@typespec/http";
import "@typespec/versioning";
import "@typespec/events";
import "@typespec/sse";

import "./models.tsp";
import "./operations.tsp";

using Http;
using Versioning;

/**
 * ChatBI 对 Enterprise AI Platform（企业 AI 平台）
 * 提供的正式公共 API。
 *
 * ChatBI 作为 Domain AI Engine（领域 AI 引擎），
 * 负责 Natural Language Query（自然语言查询）
 * 和 Business Analysis（经营分析）等领域能力。
 */
@service(#{
  title: "ChatBI Platform API",
})
@versioned(ChatBI.PlatformIntegration.Versions)
@useAuth(BearerAuth)
namespace ChatBI.PlatformIntegration;


/**
 * ChatBI Platform API 的正式版本。
 *
 * API 从第一个版本开始进入版本管理。
 * Breaking Change（破坏性变更）通过新版本演进。
 */
enum Versions {
  v2026_08_12: "2026-08-12",
}