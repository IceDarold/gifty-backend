from typing import Optional, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import ComputeTask
from app.schemas.compute import (
    ComputeTaskResponse,
    ComputeTaskResultSubmit,
    WorkerTasksResponse
)
from app.auth.dependencies import verify_internal_token

router = APIRouter(prefix="/internal/workers", tags=["workers"])


@router.get("/tasks", response_model=WorkerTasksResponse)
async def get_tasks(
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    limit: int = Query(10, ge=1, le=100, description="Number of tasks to fetch"),
    worker_id: str = Query(..., description="Worker identifier"),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token)
):
    """
    Poll for pending compute tasks.
    Marks fetched tasks as 'processing' and assigns them to the worker.
    """
    # Build query for pending tasks
    query = select(ComputeTask).where(ComputeTask.status == "pending")
    
    if task_type:
        query = query.where(ComputeTask.task_type == task_type)
    
    query = query.order_by(ComputeTask.created_at).limit(limit)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # Mark tasks as processing and assign to worker
    task_ids = [task.id for task in tasks]
    if task_ids:
        await db.execute(
            update(ComputeTask)
            .where(ComputeTask.id.in_(task_ids))
            .values(
                status="processing",
                worker_id=worker_id,
                started_at=datetime.utcnow()
            )
        )
        await db.commit()
        
        # Refresh tasks to get updated values
        for task in tasks:
            await db.refresh(task)
    
    return WorkerTasksResponse(
        tasks=[ComputeTaskResponse.model_validate(task) for task in tasks],
        count=len(tasks)
    )


@router.post("/tasks/{task_id}/result")
async def submit_task_result(
    task_id: UUID,
    result_data: ComputeTaskResultSubmit,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token)
):
    """
    Submit the result of a completed task.
    Updates task status to 'completed' or 'failed'.
    """
    # Fetch the task
    result = await db.execute(
        select(ComputeTask).where(ComputeTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["processing", "pending"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update task with status '{task.status}'"
        )
    
    # Update task
    task.status = result_data.status
    task.result = result_data.result
    task.error = result_data.error
    task.completed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(task)
    
    return ComputeTaskResponse.model_validate(task)
