"""Tests for SGP Help Agent."""

import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock


class TestSGPHelpAgent:
    """Test suite for SGP Help Agent workflow and activities."""

    @pytest.mark.asyncio
    async def test_setup_sgp_repos_creates_directories(self, tmp_path):
        """Test that setup_sgp_repos creates required directories."""
        from project.activities import setup_sgp_repos

        task_id = "test-task-123"
        workspace_root = str(tmp_path)

        # Mock git commands to avoid actual cloning
        with patch('project.activities.run_git_command', new_callable=AsyncMock) as mock_git:
            mock_git.return_value = (0, "", "")

            result = await setup_sgp_repos(
                task_id=task_id,
                workspace_root=workspace_root,
                repos=["https://github.com/test/repo.git"],
            )

            # Check directories were created
            assert os.path.exists(os.path.join(workspace_root, ".repos-cache"))
            assert os.path.exists(os.path.join(workspace_root, task_id, "repos"))

            # Check return path is correct
            assert result == os.path.join(workspace_root, task_id, "repos")

    @pytest.mark.asyncio
    async def test_setup_sgp_repos_clones_to_cache(self, tmp_path):
        """Test that repos are cloned to cache on first run."""
        from project.activities import setup_sgp_repos

        task_id = "test-task-456"
        workspace_root = str(tmp_path)
        test_repo = "https://github.com/test/repo.git"

        with patch('project.activities.run_git_command', new_callable=AsyncMock) as mock_git:
            mock_git.return_value = (0, "", "")

            await setup_sgp_repos(
                task_id=task_id,
                workspace_root=workspace_root,
                repos=[test_repo],
            )

            # Verify git clone was called for cache
            calls = [str(call) for call in mock_git.call_args_list]
            assert any("clone" in call and "--depth=1" in call for call in calls)

    @pytest.mark.asyncio
    async def test_setup_sgp_repos_updates_existing_cache(self, tmp_path):
        """Test that existing cache is updated with git fetch."""
        from project.activities import setup_sgp_repos

        task_id = "test-task-789"
        workspace_root = str(tmp_path)
        test_repo = "https://github.com/test/repo.git"

        # Create cache directory to simulate existing cache
        cache_dir = os.path.join(workspace_root, ".repos-cache", "repo")
        os.makedirs(cache_dir, exist_ok=True)

        with patch('project.activities.run_git_command', new_callable=AsyncMock) as mock_git:
            mock_git.return_value = (0, "", "")

            await setup_sgp_repos(
                task_id=task_id,
                workspace_root=workspace_root,
                repos=[test_repo],
            )

            # Verify git fetch was called to update cache
            calls = [str(call) for call in mock_git.call_args_list]
            assert any("fetch" in call for call in calls)

    @pytest.mark.asyncio
    async def test_clone_or_update_repo_handles_errors(self, tmp_path):
        """Test that clone_or_update_repo handles git errors gracefully."""
        from project.activities import clone_or_update_repo

        test_repo = "https://github.com/test/repo.git"
        cache_path = str(tmp_path / "cache")
        task_path = str(tmp_path / "task")

        with patch('project.activities.run_git_command', new_callable=AsyncMock) as mock_git:
            # Simulate git clone failure
            mock_git.side_effect = RuntimeError("Git clone failed")

            with pytest.raises(RuntimeError, match="Git clone failed"):
                await clone_or_update_repo(test_repo, cache_path, task_path)

    def test_workflow_state_initialization(self):
        """Test that workflow state model initializes correctly."""
        from project.workflow import StateModel

        state = StateModel()

        assert state.claude_session_id is None
        assert state.turn_number == 0
        assert state.repos_ready is False
        assert state.repos_path is None

    def test_workflow_state_updates(self):
        """Test that workflow state can be updated."""
        from project.workflow import StateModel

        state = StateModel()

        # Update state
        state.claude_session_id = "session-123"
        state.turn_number = 5
        state.repos_ready = True
        state.repos_path = "/path/to/repos"

        assert state.claude_session_id == "session-123"
        assert state.turn_number == 5
        assert state.repos_ready is True
        assert state.repos_path == "/path/to/repos"

    @pytest.mark.asyncio
    async def test_run_git_command_success(self):
        """Test run_git_command with successful execution."""
        from project.activities import run_git_command

        with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_proc:
            mock_process = MagicMock()
            mock_process.communicate.return_value = (b"output", b"")
            mock_process.returncode = 0
            mock_proc.return_value = mock_process

            returncode, stdout, stderr = await run_git_command(["git", "status"])

            assert returncode == 0
            assert stdout == "output"
            assert stderr == ""

    @pytest.mark.asyncio
    async def test_run_git_command_failure(self):
        """Test run_git_command with failed execution."""
        from project.activities import run_git_command

        with patch('asyncio.create_subprocess_exec', new_callable=AsyncMock) as mock_proc:
            mock_process = MagicMock()
            mock_process.communicate.return_value = (b"", b"error message")
            mock_process.returncode = 1
            mock_proc.return_value = mock_process

            with pytest.raises(RuntimeError, match="Command failed"):
                await run_git_command(["git", "invalid"], check=True)

    def test_default_repos_configured(self):
        """Test that default SGP repos are configured."""
        from project.activities import DEFAULT_SGP_REPOS

        assert len(DEFAULT_SGP_REPOS) == 3
        assert "https://github.com/scaleapi/scaleapi.git" in DEFAULT_SGP_REPOS
        assert "https://github.com/scaleapi/sgp.git" in DEFAULT_SGP_REPOS
        assert "https://github.com/scaleapi/sgp-solutions.git" in DEFAULT_SGP_REPOS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
