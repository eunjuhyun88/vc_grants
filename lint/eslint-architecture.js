/**
 * eslint-architecture.js
 * 아키텍처 불변성을 코드로 강제하는 ESLint 커스텀 규칙
 *
 * 설치: npm install --save-dev eslint
 * 사용: eslint.config.js 에 import해서 사용 (아래 참고)
 *
 * 강제 규칙:
 *  1. ui → repository 직접 import 금지
 *  2. servers/ 밖에서 callMCPTool 직접 호출 금지
 *  3. 에러 메시지에 복구 지침 없으면 경고
 */

// ── 규칙 1: ui 레이어 의존성 강제 ─────────────────────────
const noUiToRepository = {
  meta: {
    type: "error",
    docs: {
      description: "ui 레이어에서 repository 직접 import 금지. service를 통해 접근하세요.",
      url: "ARCHITECTURE.md",
    },
    messages: {
      violation:
        "[ARCH-001] ui 레이어에서 repository 직접 import 감지됨: '{{path}}'\n" +
        "수정: service 레이어를 통해 접근하세요.\n" +
        "참고: ARCHITECTURE.md § 레이어 의존성",
    },
  },
  create(context) {
    const filename = context.getFilename();
    const isUiLayer =
      filename.includes("/ui/") ||
      filename.includes("\\ui\\") ||
      filename.endsWith(".svelte");

    if (!isUiLayer) return {};

    return {
      ImportDeclaration(node) {
        const importPath = node.source.value;
        if (
          importPath.includes("/repository") ||
          importPath.includes("\\repository") ||
          importPath.includes("Repository")
        ) {
          context.report({
            node,
            messageId: "violation",
            data: { path: importPath },
          });
        }
      },
    };
  },
};

// ── 규칙 2: callMCPTool 직접 호출 금지 ────────────────────
const noDirectMCPCall = {
  meta: {
    type: "error",
    docs: {
      description: "servers/ 밖에서 callMCPTool 직접 호출 금지.",
    },
    messages: {
      violation:
        "[ARCH-002] servers/ 밖에서 callMCPTool 직접 호출 감지됨\n" +
        "수정: servers/{서버명}/{툴명}.ts 파일을 통해 호출하세요.\n" +
        "참고: AGENTS.md § MCP 툴 사용",
    },
  },
  create(context) {
    const filename = context.getFilename();
    const isInsideServers =
      filename.includes("/servers/") ||
      filename.includes("\\servers\\");

    if (isInsideServers) return {};

    return {
      CallExpression(node) {
        const callee = node.callee;
        if (
          callee.type === "Identifier" &&
          callee.name === "callMCPTool"
        ) {
          context.report({ node, messageId: "violation" });
        }
      },
    };
  },
};

// ── 규칙 3: 에러 메시지 품질 경고 ─────────────────────────
const requireRecoverableError = {
  meta: {
    type: "warn",
    docs: {
      description: "throw new Error()에 복구 지침이 없으면 경고.",
    },
    messages: {
      missing:
        "[ERR-001] 에러 메시지에 복구 지침이 없습니다.\n" +
        "권장 형식: '[CODE] 무엇이 잘못됐나\\n수정: 어떻게 고치나\\n예시: ...'",
    },
  },
  create(context) {
    return {
      ThrowStatement(node) {
        if (
          node.argument?.type === "NewExpression" &&
          node.argument.callee?.name === "Error"
        ) {
          const arg = node.argument.arguments?.[0];
          if (arg?.type === "Literal" && typeof arg.value === "string") {
            const msg = arg.value;
            // 복구 지침 키워드 없으면 경고
            const hasRecovery =
              msg.includes("수정:") ||
              msg.includes("Fix:") ||
              msg.includes("복구") ||
              msg.includes("recovery") ||
              msg.includes("시도:");
            if (!hasRecovery) {
              context.report({ node, messageId: "missing" });
            }
          }
        }
      },
    };
  },
};

// ── Export ────────────────────────────────────────────────
module.exports = {
  rules: {
    "no-ui-to-repository": noUiToRepository,
    "no-direct-mcp-call": noDirectMCPCall,
    "require-recoverable-error": requireRecoverableError,
  },
};

/**
 * ── 사용법 ─────────────────────────────────────────────────
 *
 * eslint.config.js:
 *
 * import architecturePlugin from "./eslint-architecture.js";
 *
 * export default [
 *   {
 *     plugins: { architecture: architecturePlugin },
 *     rules: {
 *       "architecture/no-ui-to-repository": "error",
 *       "architecture/no-direct-mcp-call": "error",
 *       "architecture/require-recoverable-error": "warn",
 *     },
 *   },
 * ];
 *
 * package.json scripts:
 *
 * "scripts": {
 *   "lint": "eslint src/ servers/ --ext .ts,.svelte",
 *   "lint:arch": "eslint src/ servers/ --rule 'architecture/*: error'",
 *   "typecheck": "tsc --noEmit",
 *   "check": "npm run lint && npm run typecheck"
 * }
 */
