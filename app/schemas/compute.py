from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class ComputeTaskCreate(BaseModel):
    """Schema for creating a new compute task."""
    task_type: str = Field(..., description="Type of task: 'embedding' or 'rerank'")
    priority: str = Field(default="low", description="Priority: 'low' or 'high'")
    payload: Dict[str, Any] = Field(..., description="Task input data")


class ComputeTaskResponse(BaseModel):
    """Schema for compute task response."""
    id: UUID
    task_type: str
    priority: str
    status: str
    payload: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ComputeTaskResultSubmit(BaseModel):
    """Schema for submitting task results."""
    status: str = Field(..., description="'completed' or 'failed'")
    result: Optional[Dict[str, Any]] = Field(None, description="Task output data")
    error: Optional[str] = Field(None, description="Error message if failed")


class WorkerTasksResponse(BaseModel):
    """Schema for batch task retrieval."""
    tasks: List[ComputeTaskResponse]
    count: int
