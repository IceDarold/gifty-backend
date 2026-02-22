
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.jobs.parsing_scheduler import run_parsing_scheduler, activate_discovered_sources

@pytest.mark.asyncio
async def test_run_parsing_scheduler_success():
    # Mock sources
    mock_source = MagicMock()
    mock_source.id = 1
    mock_source.url = "http://example.com"
    mock_source.site_key = "example"
    mock_source.type = "site"
    mock_source.strategy = "static"
    mock_source.config = {}
    
    # Mock repository
    mock_repo = MagicMock()
    mock_repo.get_due_sources = AsyncMock(return_value=[mock_source])
    mock_repo.set_queued = AsyncMock()
    
    # Mock context manager and other dependencies
    with patch("app.jobs.parsing_scheduler.get_session_context") as mock_ctx:
        mock_ctx.return_value.__aenter__.return_value = AsyncMock()
        with patch("app.jobs.parsing_scheduler.ParsingRepository", return_value=mock_repo):
            with patch("app.jobs.parsing_scheduler.publish_parsing_task", return_value=True) as mock_publish:
                
                await run_parsing_scheduler()
                
                mock_repo.get_due_sources.assert_called_once_with(limit=20)
                mock_publish.assert_called_once()
                mock_repo.set_queued.assert_called_once_with(1)

@pytest.mark.asyncio
async def test_run_parsing_scheduler_empty():
    mock_repo = MagicMock()
    mock_repo.get_due_sources = AsyncMock(return_value=[])
    
    with patch("app.jobs.parsing_scheduler.get_session_context") as mock_ctx:
        mock_ctx.return_value.__aenter__.return_value = AsyncMock()
        with patch("app.jobs.parsing_scheduler.ParsingRepository", return_value=mock_repo):
            with patch("app.jobs.parsing_scheduler.publish_parsing_task") as mock_publish:
                
                await run_parsing_scheduler()
                
                mock_repo.get_due_sources.assert_called_once()
                mock_publish.assert_not_called()

@pytest.mark.asyncio
async def test_activate_discovered_sources():
    mock_source = MagicMock()
    mock_source.id = 101
    
    mock_repo = MagicMock()
    mock_repo.count_discovered_today = AsyncMock(return_value=10)
    mock_repo.get_discovered_sources = AsyncMock(return_value=[mock_source])
    mock_repo.activate_sources = AsyncMock()
    
    with patch("app.jobs.parsing_scheduler.get_session_context") as mock_ctx:
        mock_ctx.return_value.__aenter__.return_value = AsyncMock()
        with patch("app.jobs.parsing_scheduler.ParsingRepository", return_value=mock_repo):
            
            await activate_discovered_sources()
            
            mock_repo.count_discovered_today.assert_called_once()
            mock_repo.get_discovered_sources.assert_called_once_with(limit=190)
            mock_repo.activate_sources.assert_called_once_with([101])

@pytest.mark.asyncio
async def test_activate_discovered_sources_quota_full():
    mock_repo = MagicMock()
    mock_repo.count_discovered_today = AsyncMock(return_value=200)
    
    with patch("app.jobs.parsing_scheduler.get_session_context") as mock_ctx:
        mock_ctx.return_value.__aenter__.return_value = AsyncMock()
        with patch("app.jobs.parsing_scheduler.ParsingRepository", return_value=mock_repo):
            
            await activate_discovered_sources()
            
            mock_repo.count_discovered_today.assert_called_once()
            mock_repo.get_discovered_sources.assert_not_called()
