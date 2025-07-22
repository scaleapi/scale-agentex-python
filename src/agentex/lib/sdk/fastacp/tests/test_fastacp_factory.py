import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentex.lib.sdk.fastacp.base.base_acp_server import BaseACPServer
from agentex.lib.sdk.fastacp.fastacp import FastACP
from agentex.lib.sdk.fastacp.impl.agentic_base_acp import AgenticBaseACP
from agentex.lib.sdk.fastacp.impl.sync_acp import SyncACP
from agentex.lib.sdk.fastacp.impl.temporal_acp import TemporalACP
from agentex.lib.types.fastacp import (
    AgenticACPConfig,
    AgenticBaseACPConfig,
    SyncACPConfig,
    TemporalACPConfig,
)


class TestFastACPInitialization:
    """Test FastACP basic functionality"""

    def test_factory_class_exists(self):
        """Test that FastACP class exists and is properly structured"""
        assert hasattr(FastACP, "create")
        assert hasattr(FastACP, "create_sync_acp")
        assert hasattr(FastACP, "create_agentic_acp")


class TestSyncACPCreation:
    """Test SyncACP creation through factory"""

    @pytest.mark.asyncio
    async def test_create_sync_acp_direct_method(self):
        """Test creating SyncACP using direct method"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            sync_acp = FastACP.create_sync_acp()

            assert isinstance(sync_acp, SyncACP)
            assert isinstance(sync_acp, BaseACPServer)
            assert hasattr(sync_acp, "_handlers")

    @pytest.mark.asyncio
    async def test_create_sync_acp_with_config(self):
        """Test creating SyncACP with configuration"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = SyncACPConfig()
            sync_acp = FastACP.create_sync_acp(config=config)

            assert isinstance(sync_acp, SyncACP)

    @pytest.mark.asyncio
    async def test_create_sync_acp_via_generic_create(self):
        """Test creating SyncACP via generic create method"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            sync_acp = FastACP.create("sync")

            assert isinstance(sync_acp, SyncACP)

    @pytest.mark.asyncio
    async def test_create_sync_acp_via_generic_create_with_config(self):
        """Test creating SyncACP via generic create method with config"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = SyncACPConfig()
            sync_acp = FastACP.create("sync", config=config)

            assert isinstance(sync_acp, SyncACP)

    @pytest.mark.asyncio
    async def test_create_sync_acp_with_enum(self):
        """Test creating SyncACP using ACPType enum"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            sync_acp = FastACP.create("sync")

            assert isinstance(sync_acp, SyncACP)

    @pytest.mark.asyncio
    async def test_create_sync_acp_with_kwargs(self):
        """Test creating SyncACP with additional kwargs"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            sync_acp = FastACP.create_sync_acp(custom_param="test_value")

            assert isinstance(sync_acp, SyncACP)


class TestAgenticBaseACPCreation:
    """Test AgenticBaseACP creation through factory"""

    @pytest.mark.asyncio
    async def test_create_agentic_base_acp_direct_method(self):
        """Test creating AgenticBaseACP using direct method"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = AgenticACPConfig(type="base")
            agentic_acp = FastACP.create_agentic_acp(config=config)

            assert isinstance(agentic_acp, AgenticBaseACP)
            assert isinstance(agentic_acp, BaseACPServer)

    @pytest.mark.asyncio
    async def test_create_agentic_base_acp_with_specific_config(self):
        """Test creating AgenticBaseACP with AgenticBaseACPConfig"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = AgenticBaseACPConfig(type="base")
            agentic_acp = FastACP.create_agentic_acp(config=config)

            assert isinstance(agentic_acp, AgenticBaseACP)

    @pytest.mark.asyncio
    async def test_create_agentic_base_acp_via_generic_create(self):
        """Test creating AgenticBaseACP via generic create method"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = AgenticACPConfig(type="base")
            agentic_acp = FastACP.create("agentic", config=config)

            assert isinstance(agentic_acp, AgenticBaseACP)

    @pytest.mark.asyncio
    async def test_create_agentic_base_acp_with_enum(self):
        """Test creating AgenticBaseACP using ACPType enum"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = AgenticACPConfig(type="base")
            agentic_acp = FastACP.create("agentic", config=config)

            assert isinstance(agentic_acp, AgenticBaseACP)


class TestAgenticTemporalACPCreation:
    """Test AgenticTemporalACP (TemporalACP) creation through factory"""

    @pytest.mark.asyncio
    async def test_create_temporal_acp_direct_method(self):
        """Test creating TemporalACP using direct method"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = AgenticACPConfig(type="temporal")

            # Mock the TemporalACP.create method since it requires temporal dependencies
            with patch.object(TemporalACP, "create", new_callable=AsyncMock) as mock_create:
                mock_temporal_instance = MagicMock(spec=TemporalACP)
                mock_create.return_value = mock_temporal_instance

                temporal_acp = FastACP.create_agentic_acp(config=config)

                assert temporal_acp == mock_temporal_instance
                mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_temporal_acp_with_temporal_config(self):
        """Test creating TemporalACP with TemporalACPConfig"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = TemporalACPConfig(type="temporal", temporal_address="localhost:7233")

            with patch.object(TemporalACP, "create", new_callable=AsyncMock) as mock_create:
                mock_temporal_instance = MagicMock(spec=TemporalACP)
                mock_create.return_value = mock_temporal_instance

                temporal_acp = FastACP.create_agentic_acp(config=config)

                assert temporal_acp == mock_temporal_instance
                # Verify temporal_address was passed
                mock_create.assert_called_once_with(temporal_address="localhost:7233")

    @pytest.mark.asyncio
    async def test_create_temporal_acp_via_generic_create(self):
        """Test creating TemporalACP via generic create method"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = AgenticACPConfig(type="temporal")

            with patch.object(TemporalACP, "create", new_callable=AsyncMock) as mock_create:
                mock_temporal_instance = MagicMock(spec=TemporalACP)
                mock_create.return_value = mock_temporal_instance

                temporal_acp = FastACP.create("agentic", config=config)

                assert temporal_acp == mock_temporal_instance

    @pytest.mark.asyncio
    async def test_create_temporal_acp_with_custom_address(self):
        """Test creating TemporalACP with custom temporal address"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = TemporalACPConfig(type="temporal", temporal_address="custom-temporal:9999")

            with patch.object(TemporalACP, "create", new_callable=AsyncMock) as mock_create:
                mock_temporal_instance = MagicMock(spec=TemporalACP)
                mock_create.return_value = mock_temporal_instance

                FastACP.create_agentic_acp(config=config)

                mock_create.assert_called_once_with(temporal_address="custom-temporal:9999")


class TestConfigurationValidation:
    """Test configuration validation and error handling"""

    @pytest.mark.asyncio
    async def test_agentic_requires_config(self):
        """Test that agentic ACP creation requires configuration"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            with pytest.raises(ValueError, match="AgenticACPConfig is required"):
                FastACP.create("agentic")

    @pytest.mark.asyncio
    async def test_agentic_requires_correct_config_type(self):
        """Test that agentic ACP creation requires AgenticACPConfig type"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            sync_config = SyncACPConfig()

            with pytest.raises(ValueError, match="AgenticACPConfig is required"):
                FastACP.create("agentic", config=sync_config)

    @pytest.mark.asyncio
    async def test_agentic_direct_method_requires_config(self):
        """Test that direct agentic method requires configuration"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            # This should raise TypeError since config is required parameter
            with pytest.raises(TypeError):
                FastACP.create_agentic_acp()

    def test_invalid_acp_type_string(self):
        """Test that invalid ACP type string raises ValueError"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            with pytest.raises(ValueError):
                asyncio.run(FastACP.create("invalid_type"))

    def test_invalid_agentic_type_in_config(self):
        """Test that invalid agentic type in config raises ValueError"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            # This should raise ValueError during config creation
            with pytest.raises(ValueError):
                AgenticACPConfig(type="invalid_agentic_type")

    @pytest.mark.asyncio
    async def test_unsupported_acp_type_enum(self):
        """Test handling of unsupported ACP type enum values"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            # Create a mock enum value that's not supported
            with patch("agentex.sdk.fastacp.fastacp.ACPType") as mock_enum:
                mock_enum.SYNC = "sync"
                mock_enum.AGENTIC = "agentic"
                unsupported_type = "unsupported"

                with pytest.raises(ValueError, match="Unsupported ACP type"):
                    FastACP.create(unsupported_type)


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.mark.asyncio
    async def test_sync_acp_creation_failure(self):
        """Test handling of SyncACP creation failure"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            with patch.object(SyncACP, "create", side_effect=Exception("Creation failed")):
                with pytest.raises(Exception, match="Creation failed"):
                    FastACP.create_sync_acp()

    @pytest.mark.asyncio
    async def test_agentic_acp_creation_failure(self):
        """Test handling of AgenticACP creation failure"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = AgenticACPConfig(type="base")

            with patch.object(AgenticBaseACP, "create", side_effect=Exception("Creation failed")):
                with pytest.raises(Exception, match="Creation failed"):
                    FastACP.create_agentic_acp(config=config)

    @pytest.mark.asyncio
    async def test_temporal_acp_creation_failure(self):
        """Test handling of TemporalACP creation failure"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            config = AgenticACPConfig(type="temporal")

            with patch.object(
                TemporalACP, "create", side_effect=Exception("Temporal connection failed")
            ):
                with pytest.raises(Exception, match="Temporal connection failed"):
                    FastACP.create_agentic_acp(config=config)


class TestIntegrationScenarios:
    """Test integration scenarios and real-world usage patterns"""

    @pytest.mark.asyncio
    async def test_create_all_acp_types(self):
        """Test creating all supported ACP types"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            # Create SyncACP
            sync_acp = FastACP.create("sync")
            assert isinstance(sync_acp, SyncACP)

            # Create AgenticBaseACP
            base_config = AgenticACPConfig(type="base")
            agentic_base = FastACP.create("agentic", config=base_config)
            assert isinstance(agentic_base, AgenticBaseACP)

            # Create TemporalACP (mocked)
            temporal_config = AgenticACPConfig(type="temporal")
            with patch.object(TemporalACP, "create", new_callable=AsyncMock) as mock_create:
                mock_temporal_instance = MagicMock(spec=TemporalACP)
                mock_create.return_value = mock_temporal_instance

                temporal_acp = FastACP.create("agentic", config=temporal_config)
                assert temporal_acp == mock_temporal_instance

    @pytest.mark.asyncio
    async def test_configuration_driven_creation(self):
        """Test configuration-driven ACP creation"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            configs = [
                ("sync", None),
                ("agentic", AgenticACPConfig(type="base")),
                ("agentic", TemporalACPConfig(type="temporal", temporal_address="localhost:7233")),
            ]

            created_acps = []

            for acp_type, config in configs:
                if acp_type == "agentic" and config.type == "temporal":
                    # Mock temporal creation
                    with patch.object(TemporalACP, "create", new_callable=AsyncMock) as mock_create:
                        mock_temporal_instance = MagicMock(spec=TemporalACP)
                        mock_create.return_value = mock_temporal_instance

                        acp = FastACP.create(acp_type, config=config)
                        created_acps.append(acp)
                else:
                    acp = FastACP.create(acp_type, config=config)
                    created_acps.append(acp)

            assert len(created_acps) == 3
            assert isinstance(created_acps[0], SyncACP)
            assert isinstance(created_acps[1], AgenticBaseACP)
            # Third one is mocked TemporalACP

    @pytest.mark.asyncio
    async def test_factory_with_custom_kwargs(self):
        """Test factory methods with custom keyword arguments"""
        with patch.dict("os.environ", {"AGENTEX_BASE_URL": ""}):
            # Test sync with kwargs
            sync_acp = FastACP.create_sync_acp(custom_param="test")
            assert isinstance(sync_acp, SyncACP)

            # Test agentic base with kwargs
            config = AgenticACPConfig(type="base")
            agentic_acp = FastACP.create_agentic_acp(config=config, custom_param="test")
            assert isinstance(agentic_acp, AgenticBaseACP)
