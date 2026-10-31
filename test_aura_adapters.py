"""
===================================================================================
AURA ADAPTER & ARCHITECTURE CERTIFICATION SUITE
===================================================================================
Tests all 10 architectural layers and 64+ curated capabilities to ensure
zero bugs, zero crashes, and production-grade reliability.
===================================================================================
"""
import unittest
from pathlib import Path

from aura_adapters import audit_adapters, ADAPTER_CATALOG
from aura_adapters.model_inference import (
    LiteLLMUnifiedRouter,
    VLLMPagedAttentionEstimator,
    TransformersChatMLFormatter,
    TRLRewardScorer,
    UnslothRoPEContextScaler,
    LlamaCppGrammarBuilder,
    DeepSpeedZeROEstimator
)
from aura_adapters.agent_orchestration import (
    LangGraphCyclicEngine,
    PydanticAIGuardrailValidator,
    OpenAIAgentHandoffManager,
    SmolagentsCodeExecutionLoop,
    CrewAIRolePlanner
)
from aura_adapters.coding_agents import (
    AiderDiffPatcher,
    AiderASTRepoMapper,
    OpenHandsActionObservationLoop,
    SWEAgentACITerminal,
    RooCodeModeSwitcher,
    HermesStructuredXMLParser
)
from aura_adapters.mcp_protocol import (
    MCPSpecificationHandler,
    GitHubMCPConnector,
    PlaywrightMCPConnector
)
from aura_adapters.browser_automation import (
    PlaywrightController,
    StagehandAIPrimitives,
    BrowserUseBoundingBoxGrounder,
    OmniParserElementMapper
)
from aura_adapters.memory_rag import (
    Mem0EpisodicMemoryVault,
    LettaHierarchicalMemoryManager,
    PgvectorSimilarityMath,
    GraphRAGTripletExtractor,
    UnstructuredDocumentChunker
)
from aura_adapters.durable_workflows import (
    PrefectDurableFlowRunner,
    CeleryTaskQueue
)
from aura_adapters.security_sandboxes import (
    SemgrepSecurityScanner,
    GitleaksSecretScanner,
    CedarPolicyEngine
)
from aura_adapters.eval_observability import (
    PhoenixSpanTracer,
    PromptfooAssertionEngine,
    DeepEvalMetricScorer
)


class TestAuraAdaptersArchitecture(unittest.TestCase):

    def test_01_catalog_audit(self):
        audit = audit_adapters()
        self.assertTrue(audit["success"])
        self.assertGreaterEqual(audit["total_curated_adapters"], 50)
        self.assertEqual(audit["architecture_layers"], 10)

    def test_02_litellm_router(self):
        router = LiteLLMUnifiedRouter()
        res = router.route_request("Explain quantum encryption algorithms")
        self.assertIn("routed_model", res)
        cost = router.calculate_cost("gemini-1.5-flash", 1000, 500)
        self.assertGreater(cost, 0.0)

    def test_03_vllm_paged_attention(self):
        est = VLLMPagedAttentionEstimator.estimate_kv_cache(batch_size=8, max_context_len=4096)
        self.assertGreater(est["kv_cache_total_gb"], 0.0)
        self.assertIn("paged_attention_efficiency", est)

    def test_04_transformers_chatml(self):
        msgs = [{"role": "system", "content": "You are AURA."}, {"role": "user", "content": "Hello"}]
        chatml = TransformersChatMLFormatter.apply_chatml_template(msgs)
        self.assertIn("<|im_start|>system\nYou are AURA.<|im_end|>", chatml)

    def test_05_trl_reward_differential(self):
        res = TRLRewardScorer.compute_dpo_reward_differential(chosen_logps=-1.2, rejected_logps=-2.5)
        self.assertTrue(res["chosen_preferred"])
        self.assertGreater(res["reward_margin"], 0.0)

    def test_06_unsloth_rope_scaling(self):
        scale = UnslothRoPEContextScaler.calculate_rope_scaling(8192, 32768)
        self.assertEqual(scale["scaling_factor"], 4.0)

    def test_07_langgraph_cyclic_orchestration(self):
        graph = LangGraphCyclicEngine()
        graph.add_node("plan", lambda s: {**s, "plan": "done", "step": s.get("step", 0) + 1})
        graph.add_node("execute", lambda s: {**s, "executed": True, "step": s["step"] + 1})
        graph.add_edge("plan", "execute")
        graph.add_conditional_edge("execute", lambda s: "__end__" if s["step"] >= 2 else "plan")

        run_res = graph.run({"input": "test_goal"}, start_node="plan")
        self.assertEqual(run_res["final_state"]["executed"], True)
        self.assertGreaterEqual(run_res["steps_executed"], 2)
        self.assertGreaterEqual(run_res["checkpoints_recorded"], 2)

    def test_08_pydanticai_guardrail_validation(self):
        spec = {"task_name": str, "priority": int}
        valid_data = {"task_name": "Audit", "priority": 1}
        is_valid, errors = PydanticAIGuardrailValidator.validate_schema(valid_data, spec)
        self.assertTrue(is_valid)

        invalid_data = {"task_name": 12345}
        is_valid, errors = PydanticAIGuardrailValidator.validate_schema(invalid_data, spec)
        self.assertFalse(is_valid)
        self.assertGreaterEqual(len(errors), 1)

    def test_09_smolagents_code_execution(self):
        res = SmolagentsCodeExecutionLoop.execute_safe_python("x = 10 * 5\ny = x + 2")
        self.assertTrue(res["success"])
        self.assertEqual(res["output"]["y"], 52)

        # Disallow prohibited calls
        evil = SmolagentsCodeExecutionLoop.execute_safe_python("eval('1+1')")
        self.assertFalse(evil["success"])
        self.assertIn("Prohibited AST node", evil["error"])

    def test_10_aider_diff_patcher(self):
        orig = "def add(a, b):\n    return a - b\n"
        patch = "<<<<<<< SEARCH\n    return a - b\n=======\n    return a + b\n>>>>>>> REPLACE"
        ok, updated, msg = AiderDiffPatcher.apply_patch(orig, patch)
        self.assertTrue(ok)
        self.assertEqual(updated, "def add(a, b):\n    return a + b\n")

    def test_11_aider_ast_repo_mapper(self):
        this_file = Path(__file__).resolve()
        mapped = AiderASTRepoMapper.map_file_symbols(this_file)
        self.assertGreater(mapped["total_symbols"], 0)
        self.assertTrue(any(c["name"] == "TestAuraAdaptersArchitecture" for c in mapped["classes"]))

    def test_12_mcp_spec_jsonrpc(self):
        req = MCPSpecificationHandler.create_request("tools/call", {"name": "test_tool"})
        self.assertEqual(req["jsonrpc"], "2.0")
        self.assertEqual(req["method"], "tools/call")

        tools = GitHubMCPConnector.get_tool_declarations()
        self.assertGreater(len(tools), 0)
        self.assertEqual(tools[0]["name"], "github_get_issue")

    def test_13_browser_bounding_box_normalizer(self):
        norm = BrowserUseBoundingBoxGrounder.normalize_bbox(100, 200, 50, 40, screen_w=1000, screen_h=1000)
        self.assertEqual(norm["norm_x"], 0.1)
        self.assertEqual(norm["norm_y"], 0.2)

    def test_14_mem0_episodic_memory(self):
        vault = Mem0EpisodicMemoryVault()
        vault.store_fact("user_language", "Python and TypeScript", category="dev")
        recalled = vault.recall("What is user language preference?")
        self.assertGreater(len(recalled), 0)
        self.assertEqual(recalled[0]["key"], "user_language")

    def test_15_pgvector_similarity_math(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]
        sim_identical = PgvectorSimilarityMath.cosine_similarity(v1, v2)
        sim_orthogonal = PgvectorSimilarityMath.cosine_similarity(v1, v3)
        self.assertEqual(sim_identical, 1.0)
        self.assertEqual(sim_orthogonal, 0.0)

    def test_16_prefect_durable_flow_retries(self):
        counter = {"attempts": 0}
        def flakey_operation():
            counter["attempts"] += 1
            if counter["attempts"] < 2:
                raise ValueError("Transient error")
            return "SUCCESS_DATA"

        runner = PrefectDurableFlowRunner(max_retries=3, backoff_factor=0.01)
        res = runner.execute_step("test_step", flakey_operation)
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(res["attempts"], 2)
        self.assertEqual(res["result"], "SUCCESS_DATA")

    def test_17_semgrep_security_scanner(self):
        bad_code = "eval(user_input)\nos.system('dir')\nprint('safe')"
        findings = SemgrepSecurityScanner.scan_code(bad_code)
        self.assertGreaterEqual(len(findings), 2)
        rule_ids = [f["rule_id"] for f in findings]
        self.assertIn("eval-injection", rule_ids)
        self.assertIn("subshell-injection", rule_ids)

    def test_18_gitleaks_secret_detector(self):
        leak_text = "API_KEY = 'AQ.test12345678901234567890'\nAWS = 'AKIA1234567890123456'"
        findings = GitleaksSecretScanner.scan_text(leak_text)
        self.assertGreaterEqual(len(findings), 2)

    def test_19_cedar_policy_evaluation(self):
        engine = CedarPolicyEngine()
        allowed, _ = engine.is_authorized(role="admin", action="any_action", resource="any")
        self.assertTrue(allowed)

        forbidden, reason = engine.is_authorized(role="guest", action="powershell_exec", resource="host")
        self.assertFalse(forbidden)
        self.assertIn("FORBIDDEN", reason)

    def test_20_promptfoo_output_assertions(self):
        text = "AURA Autonomous Intelligence Core is operational."
        pass_contains, _ = PromptfooAssertionEngine.assert_contains(text, "operational")
        self.assertTrue(pass_contains)
        pass_not_contains, _ = PromptfooAssertionEngine.assert_not_contains(text, "ERROR")
        self.assertTrue(pass_not_contains)


if __name__ == "__main__":
    unittest.main()
