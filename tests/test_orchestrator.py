import unittest

from story_agent_workbench.orchestrator.orchestrator import orchestrate_hidden_agents


class TestOrchestrator(unittest.TestCase):
    def test_story_buddy_default(self) -> None:
        out = orchestrate_hidden_agents(
            query="我想顺一下剧情",
            mode="chat",
            base_reply="基础回复",
            text_evidence=[],
            graph_evidence=[],
            graph_results=None,
        )
        self.assertIn("orchestrator", out.agents_called)
        self.assertIn("story_buddy", out.agents_called)

    def test_critic_trigger(self) -> None:
        out = orchestrate_hidden_agents(
            query="这里会不会有冲突",
            mode="chat",
            base_reply="基础回复",
            text_evidence=[],
            graph_evidence=["A -> B"],
            graph_results={"answer_type": "relationship_between"},
        )
        self.assertIn("critic", out.agents_called)

    def test_systems_designer_trigger(self) -> None:
        out = orchestrate_hidden_agents(
            query="这个任务机制怎么设计互动",
            mode="chat",
            base_reply="基础回复",
            text_evidence=[],
            graph_evidence=[],
            graph_results=None,
        )
        self.assertIn("systems_designer", out.agents_called)


if __name__ == "__main__":
    unittest.main()
