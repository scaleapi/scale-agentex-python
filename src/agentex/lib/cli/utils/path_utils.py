from pathlib import Path
from typing import Dict

from agentex.lib.sdk.config.agent_manifest import AgentManifest
from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


class PathResolutionError(Exception):
    """An error occurred during path resolution"""


def resolve_and_validate_path(base_path: Path, configured_path: str, file_type: str) -> Path:
    """Resolve and validate a configured path"""
    path_obj = Path(configured_path)

    if path_obj.is_absolute():
        # Absolute path - resolve to canonical form
        resolved_path = path_obj.resolve()
    else:
        # Relative path - resolve relative to manifest directory
        resolved_path = (base_path / configured_path).resolve()

    # Validate the file exists
    if not resolved_path.exists():
        raise PathResolutionError(
            f"{file_type} file not found: {resolved_path}\n"
            f"  Configured path: {configured_path}\n"
            f"  Resolved from manifest: {base_path}"
        )

    # Validate it's actually a file
    if not resolved_path.is_file():
        raise PathResolutionError(f"{file_type} path is not a file: {resolved_path}")

    return resolved_path


def validate_path_security(resolved_path: Path, manifest_dir: Path) -> None:
    """Basic security validation for resolved paths"""
    try:
        # Ensure the resolved path is accessible
        resolved_path.resolve()

        # Optional: Add warnings for paths that go too far up
        try:
            # Check if path goes more than 3 levels up from manifest
            relative_to_manifest = resolved_path.relative_to(manifest_dir.parent.parent.parent)
            if str(relative_to_manifest).startswith(".."):
                logger.warning(
                    f"Path goes significantly outside project structure: {resolved_path}"
                )
        except ValueError:
            # Path is outside the tree - that's okay, just log it
            logger.info(f"Using path outside manifest directory tree: {resolved_path}")

    except Exception as e:
        raise PathResolutionError(f"Path resolution failed: {resolved_path} - {str(e)}") from e


def get_file_paths(manifest: AgentManifest, manifest_path: str) -> Dict[str, Path | None]:
    """Get resolved file paths from manifest configuration"""
    manifest_dir = Path(manifest_path).parent.resolve()

    # Use configured paths or fall back to defaults for backward compatibility
    if manifest.local_development and manifest.local_development.paths:
        paths_config = manifest.local_development.paths

        # Resolve ACP path
        acp_path = resolve_and_validate_path(manifest_dir, paths_config.acp, "ACP server")
        validate_path_security(acp_path, manifest_dir)

        # Resolve worker path if specified
        worker_path = None
        if paths_config.worker:
            worker_path = resolve_and_validate_path(
                manifest_dir, paths_config.worker, "Temporal worker"
            )
            validate_path_security(worker_path, manifest_dir)
    else:
        # Backward compatibility: use old hardcoded structure
        project_dir = manifest_dir / "project"
        acp_path = (project_dir / "acp.py").resolve()
        worker_path = (project_dir / "run_worker.py").resolve() if manifest.agent.is_temporal_agent() else None

        # Validate backward compatibility paths
        if not acp_path.exists():
            raise PathResolutionError(f"ACP file not found: {acp_path}")

        if worker_path and not worker_path.exists():
            raise PathResolutionError(f"Worker file not found: {worker_path}")

    return {
        "acp": acp_path,
        "worker": worker_path,
        "acp_dir": acp_path.parent,
        "worker_dir": worker_path.parent if worker_path else None,
    }


def calculate_uvicorn_target_for_local(acp_path: Path, manifest_dir: Path) -> str:
    """Calculate the uvicorn target path for local development"""
    # Ensure both paths are resolved to canonical form for accurate comparison
    acp_resolved = acp_path.resolve()
    manifest_resolved = manifest_dir.resolve()
    
    try:
        # Try to use path relative to manifest directory
        acp_relative = acp_resolved.relative_to(manifest_resolved)
        # Convert to module notation: project/acp.py -> project.acp
        module_path = str(acp_relative.with_suffix(''))  # Remove .py extension
        module_path = module_path.replace('/', '.')  # Convert slashes to dots
        module_path = module_path.replace('\\', '.')  # Handle Windows paths
        return module_path
    except ValueError:
        # Path cannot be made relative - use absolute file path
        logger.warning(f"ACP file {acp_resolved} cannot be made relative to manifest directory {manifest_resolved}, using absolute file path")
        return str(acp_resolved)


def calculate_docker_acp_module(manifest: AgentManifest, manifest_path: str) -> str:
    """Calculate the Python module path for the ACP file in the Docker container
    
    This should return the same module notation as local development for consistency.
    """
    # Use the same logic as local development
    manifest_dir = Path(manifest_path).parent
    
    # Get the configured ACP path (could be relative or absolute)
    if manifest.local_development and manifest.local_development.paths:
        acp_config_path = manifest.local_development.paths.acp
    else:
        acp_config_path = "project/acp.py"  # Default
    
    # Resolve to actual file path
    acp_path = resolve_and_validate_path(manifest_dir, acp_config_path, "ACP")
    
    # Use the same module calculation as local development
    return calculate_uvicorn_target_for_local(acp_path, manifest_dir)


 