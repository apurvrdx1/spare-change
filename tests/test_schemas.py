from distributor.schemas import (
    ContextFile,
    CreateTaskRequest,
    ResultStatus,
    Task,
    WebhookResult,
)


def test_task_roundtrip():
    task = Task(task_id="t1", project_slug="psf/requests", prompt="hello")
    parsed = Task.model_validate_json(task.model_dump_json())
    assert parsed.task_id == "t1"
    assert parsed.project_slug == "psf/requests"
    assert parsed.kind == "prompt"


def test_create_task_defaults():
    req = CreateTaskRequest(project_slug="psf/requests", prompt="hi")
    assert req.max_cost_usd == 0.50
    assert req.timeout_seconds == 120
    assert req.context_files == []


def test_webhook_result_roundtrip():
    result = WebhookResult(task_id="t1", agent_id="a1", status=ResultStatus.SUCCESS)
    parsed = WebhookResult.model_validate_json(result.model_dump_json())
    assert parsed.status == ResultStatus.SUCCESS


def test_context_file_in_task():
    cf = ContextFile(path="README.md", content="hello")
    task = Task(task_id="t2", project_slug="babel/babel", prompt="p", context_files=[cf])
    parsed = Task.model_validate_json(task.model_dump_json())
    assert parsed.context_files[0].path == "README.md"
    assert parsed.context_files[0].content == "hello"
