"""Custom activities for SGP Help Agent - Git repository management."""

from __future__ import annotations

import os
import asyncio
from pathlib import Path
from typing import Any

from temporalio import activity

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)

# Default SGP repositories to clone
DEFAULT_SGP_REPOS = [
    "https://github.com/scaleapi/scaleapi.git",
    "https://github.com/scaleapi/sgp.git",
    "https://github.com/scaleapi/sgp-solutions.git",
]


async def run_git_command(
    cmd: list[str],
    cwd: str | None = None,
    check: bool = True,
) -> tuple[int, str, str]:
    """Execute git command asynchronously.

    Args:
        cmd: Command and arguments to execute
        cwd: Working directory for command
        check: Whether to raise exception on non-zero exit

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    logger.debug(f"Running: {' '.join(cmd)} (cwd={cwd})")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    returncode = process.returncode or 0

    stdout_text = stdout.decode() if stdout else ""
    stderr_text = stderr.decode() if stderr else ""

    if check and returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"Return code: {returncode}\n"
            f"Stderr: {stderr_text}"
        )

    return returncode, stdout_text, stderr_text


async def clone_or_update_repo(
    repo_url: str,
    cache_path: str,
    task_path: str,
) -> None:
    """Clone repo to cache and create shallow clone for task.

    Strategy:
    1. If cache doesn't exist: clone --depth=1 to cache
    2. If cache exists: fetch origin to update
    3. Clone from cache to task workspace using file:// URL

    Args:
        repo_url: HTTPS URL of repository
        cache_path: Path to cache directory for this repo
        task_path: Path to task workspace for this repo
    """
    repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')

    logger.info(f"Setting up {repo_name}: cache={cache_path}, task={task_path}")

    # Step 1: Ensure cache is ready
    if not os.path.exists(cache_path):
        logger.info(f"Cache miss for {repo_name}, cloning...")
        await run_git_command(
            ["git", "clone", "--depth=1", repo_url, cache_path],
        )
        logger.info(f"Cached {repo_name}")
    else:
        logger.info(f"Cache hit for {repo_name}, updating...")
        try:
            await run_git_command(
                ["git", "-C", cache_path, "fetch", "origin"],
            )
            await run_git_command(
                ["git", "-C", cache_path, "reset", "--hard", "origin/HEAD"],
            )
            logger.info(f"Updated cache for {repo_name}")
        except Exception as e:
            logger.warning(f"Failed to update cache for {repo_name}: {e}")
            # Continue with existing cache

    # Step 2: Clone from cache to task workspace
    if os.path.exists(task_path):
        logger.info(f"Task workspace already has {repo_name}, skipping clone")
        return

    logger.info(f"Cloning {repo_name} to task workspace...")
    await run_git_command(
        ["git", "clone", "--depth=1", f"file://{cache_path}", task_path],
    )
    logger.info(f"Task workspace ready: {task_path}")


@activity.defn
async def setup_sgp_repos(
    task_id: str,
    workspace_root: str | None = None,
    repos: list[str] | None = None,
) -> str:
    """Clone SGP repos for task workspace with caching.

    This activity clones the specified SGP repositories into a task-specific
    workspace, using a shared cache to minimize network traffic and improve
    performance.

    Directory structure:
    - {workspace_root}/.repos-cache/{repo-name}/ - Shared cache
    - {workspace_root}/{task_id}/repos/{repo-name}/ - Task-specific clones

    Args:
        task_id: Task ID for workspace directory name
        workspace_root: Root directory for workspaces (defaults to .claude-workspace/)
        repos: List of repo URLs to clone (defaults to DEFAULT_SGP_REPOS)

    Returns:
        Absolute path to repos directory: {workspace_root}/{task_id}/repos/
    """
    if workspace_root is None:
        workspace_root = os.path.join(os.getcwd(), ".claude-workspace")

    if repos is None:
        repos = DEFAULT_SGP_REPOS

    # Create directory structure
    cache_root = os.path.join(workspace_root, ".repos-cache")
    task_repos_root = os.path.join(workspace_root, task_id, "repos")

    os.makedirs(cache_root, exist_ok=True)
    os.makedirs(task_repos_root, exist_ok=True)

    logger.info(f"Setting up SGP repos for task {task_id}")
    logger.info(f"Cache root: {cache_root}")
    logger.info(f"Task repos root: {task_repos_root}")
    logger.info(f"Repos to clone: {len(repos)}")

    # Clone each repo
    for repo_url in repos:
        repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
        cache_path = os.path.join(cache_root, repo_name)
        task_path = os.path.join(task_repos_root, repo_name)

        try:
            await clone_or_update_repo(repo_url, cache_path, task_path)
        except Exception as e:
            logger.error(f"Failed to setup {repo_name}: {e}", exc_info=True)
            raise

    logger.info(f"All repos ready: {task_repos_root}")
    return task_repos_root
