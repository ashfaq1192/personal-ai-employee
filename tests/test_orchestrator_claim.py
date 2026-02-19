"""Tests for claim manager."""

from pathlib import Path

from src.orchestrator.claim_manager import ClaimManager


class TestClaimManager:
    """Test ClaimManager functionality."""

    def test_claim_file(self, temp_vault: Path) -> None:
        """Test claiming a file by moving it."""
        mgr = ClaimManager(temp_vault)
        
        # Create file in Needs_Action
        needs_action = temp_vault / "Needs_Action"
        needs_action.mkdir(parents=True, exist_ok=True)
        test_file = needs_action / "test_item.md"
        test_file.write_text("test content", encoding="utf-8")
        
        # Claim it
        result = mgr.claim(test_file, "test_agent")
        
        assert result is True
        assert not test_file.exists()
        
        claimed_file = temp_vault / "In_Progress" / "test_agent" / "test_item.md"
        assert claimed_file.exists()

    def test_claim_nonexistent_file(self, temp_vault: Path) -> None:
        """Test claiming a file that doesn't exist."""
        mgr = ClaimManager(temp_vault)
        
        fake_file = temp_vault / "Needs_Action" / "nonexistent.md"
        result = mgr.claim(fake_file, "test_agent")
        
        assert result is False

    def test_claim_race_condition(self, temp_vault: Path) -> None:
        """Test that only one agent can claim a file."""
        mgr = ClaimManager(temp_vault)
        
        # Create file
        needs_action = temp_vault / "Needs_Action"
        needs_action.mkdir(parents=True, exist_ok=True)
        test_file = needs_action / "race_test.md"
        test_file.write_text("test", encoding="utf-8")
        
        # First agent claims
        result1 = mgr.claim(test_file, "agent1")
        assert result1 is True
        
        # Second agent tries to claim same file
        result2 = mgr.claim(test_file, "agent2")
        assert result2 is False  # File already moved

    def test_release_file(self, temp_vault: Path) -> None:
        """Test releasing a claimed file to Done."""
        mgr = ClaimManager(temp_vault)
        
        # Create and claim file
        needs_action = temp_vault / "Needs_Action"
        needs_action.mkdir(parents=True, exist_ok=True)
        test_file = needs_action / "release_test.md"
        test_file.write_text("test", encoding="utf-8")
        
        mgr.claim(test_file, "test_agent")
        
        # Release it
        result = mgr.release("release_test.md", "test_agent", "Done")
        
        assert result is True
        
        done_file = temp_vault / "Done" / "release_test.md"
        assert done_file.exists()
        
        in_progress_file = (
            temp_vault / "In_Progress" / "test_agent" / "release_test.md"
        )
        assert not in_progress_file.exists()

    def test_release_nonexistent_file(self, temp_vault: Path) -> None:
        """Test releasing a file that wasn't claimed."""
        mgr = ClaimManager(temp_vault)
        
        result = mgr.release("nonexistent.md", "test_agent")
        
        assert result is False

    def test_list_claims(self, temp_vault: Path) -> None:
        """Test listing all claims."""
        mgr = ClaimManager(temp_vault)
        
        # Create and claim files
        needs_action = temp_vault / "Needs_Action"
        needs_action.mkdir(parents=True, exist_ok=True)
        
        for i in range(3):
            test_file = needs_action / f"claim_{i}.md"
            test_file.write_text(f"content {i}", encoding="utf-8")
            mgr.claim(test_file, "agent1")
        
        claims = mgr.list_claims("agent1")
        
        assert len(claims) == 3
        assert all(c["agent"] == "agent1" for c in claims)

    def test_list_claims_all_agents(self, temp_vault: Path) -> None:
        """Test listing claims from all agents."""
        mgr = ClaimManager(temp_vault)
        
        # Create files for different agents
        needs_action = temp_vault / "Needs_Action"
        needs_action.mkdir(parents=True, exist_ok=True)
        
        for i in range(2):
            test_file = needs_action / f"agent1_{i}.md"
            test_file.write_text("content", encoding="utf-8")
            mgr.claim(test_file, "agent1")
        
        for i in range(3):
            test_file = needs_action / f"agent2_{i}.md"
            test_file.write_text("content", encoding="utf-8")
            mgr.claim(test_file, "agent2")
        
        all_claims = mgr.list_claims()
        
        assert len(all_claims) == 5

    def test_claim_creates_agent_directory(self, temp_vault: Path) -> None:
        """Test that claiming creates the agent's directory."""
        mgr = ClaimManager(temp_vault)
        
        needs_action = temp_vault / "Needs_Action"
        needs_action.mkdir(parents=True, exist_ok=True)
        test_file = needs_action / "new_agent_test.md"
        test_file.write_text("test", encoding="utf-8")
        
        agent_dir = temp_vault / "In_Progress" / "new_agent"
        assert not agent_dir.exists()
        
        mgr.claim(test_file, "new_agent")
        
        assert agent_dir.exists()
