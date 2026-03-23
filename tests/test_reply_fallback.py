import unittest

from story_agent_workbench.chat.reply_layer import generate_reply
from story_agent_workbench.graph.graph_retriever import GraphConfig
from story_agent_workbench.retrieval.text_retriever import RetrievalConfig
from story_agent_workbench.router.agent_router import route_query
from story_agent_workbench.strategy import load_strategy_config


class TestReplyFallback(unittest.TestCase):
    def test_auto_mode_switch_from_chat(self) -> None:
        strategy = load_strategy_config()
        route = route_query("给我改写建议", strategy=strategy)
        payload = generate_reply(
            query="给我改写建议",
            mode="chat",
            show_evidence=False,
            top_k=2,
            retrieval_config=RetrievalConfig(),
            graph_config=GraphConfig(),
            strategy=strategy,
            route_decision=route,
            memory_turns=[],
        )
        self.assertEqual(payload["mode"], "feedback")

    def test_weak_hit_fallback_note(self) -> None:
        strategy = load_strategy_config()
        route = route_query("不存在实体甲和不存在实体乙有什么关系？", strategy=strategy)
        payload = generate_reply(
            query="不存在实体甲和不存在实体乙有什么关系？",
            mode="critic",
            show_evidence=False,
            top_k=2,
            retrieval_config=RetrievalConfig(),
            graph_config=GraphConfig(),
            strategy=strategy,
            route_decision=route,
            memory_turns=[],
        )
        self.assertIn("fallback_reason", payload)
        self.assertTrue(payload["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
