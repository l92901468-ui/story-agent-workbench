import unittest

from story_agent_workbench.router.agent_router import route_query
from story_agent_workbench.strategy import load_strategy_config


class TestRouterStrategy(unittest.TestCase):
    def test_route_graph_with_confidence(self) -> None:
        strategy = load_strategy_config()
        route = route_query("艾琳和灰塔阵营有什么关系？", strategy=strategy)
        self.assertEqual(route["route"], "graph_retrieval")
        self.assertIn("confidence", route)
        self.assertGreaterEqual(route["confidence"], 0.3)

    def test_route_text_default(self) -> None:
        strategy = load_strategy_config()
        route = route_query("帮我改写这一段", strategy=strategy)
        self.assertEqual(route["route"], "text_retrieval")


if __name__ == "__main__":
    unittest.main()
