from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_FILE = ROOT / "agents" / "linkedin_agent.md"
SKILL_FILE = ROOT / ".opencode" / "skills" / "linkedin-poster" / "SKILL.md"


def test_agent_definition_exists():
    assert AGENT_FILE.is_file()


def test_agent_defines_hitl_policy():
    content = AGENT_FILE.read_text(encoding="utf-8")
    assert "Human in the Loop" in content
    assert "2FA" in content


def test_skill_exists_with_frontmatter():
    content = SKILL_FILE.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "name: linkedin-poster" in content
    assert "description:" in content
