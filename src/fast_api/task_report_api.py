
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Query

from src.configuration import conf
from src.classes.cls_const import TaskRole


fastapi_router = APIRouter()


@fastapi_router.get("/tasks")
async def get_tasks(
	group_id: Optional[int] = Query(None, description="Filter by task group id"),
	# creator_id: Optional[int] = Query(None, description="Filter by creator id"),
	executor_id: Optional[int] = Query(None, description="Filter by executor id"),
	stage_title: Optional[str] = Query(None, description="Filter by stage title"),
	created_from: Optional[str] = Query(None, description="Filter created_date >= ISO datetime"),
	created_to: Optional[str] = Query(None, description="Filter created_date <= ISO datetime"),
) -> List[dict]:
	"""Return list of tasks. Optional query parameter `stage_ids` is a comma separated list of stage ids.

	Response item fields:
	  - title
	  - created_date
	  - deadline
	  - closed_date
	  - stage.title
	  - group.title
	  - creator (full name or None)
	  - executor (full name or None)
	"""

	# parse created date range
	created_from_dt: Optional[datetime] = None
	created_to_dt: Optional[datetime] = None
	try:
		if created_from:
			created_from_dt = datetime.fromisoformat(created_from)
		if created_to:
			created_to_dt = datetime.fromisoformat(created_to)
	except Exception:
		created_from_dt = None
		created_to_dt = None

	# fetch tasks: if user_id specified, use DB helper to filter by user; otherwise fetch by stages
	
	tasks = await conf.bitrix_db.get_tasks_for_report(
		executor_id=executor_id, group_id=group_id, stage_title=stage_title,
		created_from_dt=created_from_dt, created_to_dt=created_to_dt
	)

	result = []
	for task in tasks:
		# find creator and executor among task_users
		creator = None
		executor = None
		# task.task_users may be loaded via relationship; fallback to empty list
		task_users = getattr(task, "task_users", []) or []
		for tu in task_users:
			if tu.role == TaskRole.CREATOR:
				creator = tu
			elif tu.role == TaskRole.EXECUTOR:
				executor = tu

		item = {
			"title": task.title,
			"created_date": task.created_date.isoformat() if getattr(task, "created_date", None) else None,
			"deadline": task.deadline.isoformat() if getattr(task, "deadline", None) else None,
			"closed_date": task.closed_date.isoformat() if getattr(task, "closed_date", None) else None,
			"stage": getattr(task.stage, "title", None),
			"group": getattr(task.group, "title", None),
			"creator": getattr(creator.user, "full_name", None) if creator else None,
			"executor": getattr(executor.user, "full_name", None) if executor else None,
		}

		result.append(item)

	return result


@fastapi_router.get("/stages")
async def list_stages() -> List[dict]:
	"""Return list of stages with value `title`."""
	stages = await conf.bitrix_db.get_task_stage()
	return [{"title": s.title} for s in stages]


@fastapi_router.get("/groups")
async def list_groups() -> List[dict]:
	"""Return list of task groups with `id` and `title`."""
	groups = await conf.bitrix_db.get_task_group()
	return [{"id": g.id, "title": g.title} for g in groups]


@fastapi_router.get("/users")
async def list_users() -> List[dict]:
	"""Return list of users with `id` and `full_name`."""
	users = await conf.bitrix_db.get_users()
	return [{"id": u.id, "full_name": u.full_name} for u in users]
