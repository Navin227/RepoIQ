import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "backend_proxy.py"
SPEC = importlib.util.spec_from_file_location("backend_proxy", MODULE_PATH)
backend_proxy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend_proxy)


class FakeEC2:
    def __init__(self, public_ip: str | None = "203.0.113.10") -> None:
        self.public_ip = public_ip
        self.filters = None

    def describe_instances(self, Filters: list[dict]) -> dict:
        self.filters = Filters
        if not self.public_ip:
            return {"Reservations": []}
        return {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "PublicIpAddress": self.public_ip,
                            "LaunchTime": "2026-10-11T00:00:00Z",
                        }
                    ]
                }
            ]
        }


class FakeResponse:
    status = 200
    headers = {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return b'{"status":"ok"}'

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _event(method: str, path: str, query: str = "", body: str | None = None) -> dict:
    return {
        "rawPath": path,
        "rawQueryString": query,
        "headers": {
            "content-type": "application/json",
            "origin": "https://main.d20r18yhh140ff.amplifyapp.com",
        },
        "body": body,
        "requestContext": {"http": {"method": method}},
    }


def test_search_is_forwarded_to_current_instance_with_query(monkeypatch) -> None:
    fake_ec2 = FakeEC2()
    monkeypatch.setattr(backend_proxy, "ec2", fake_ec2)
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(backend_proxy, "urlopen", fake_urlopen)

    response = backend_proxy.lambda_handler(
        _event("GET", "/search", "q=healthcare%20platforms"),
        None,
    )

    assert response["statusCode"] == 200
    request, timeout = requests[0]
    assert request.full_url == (
        "http://203.0.113.10:80/search?q=healthcare%20platforms"
    )
    assert request.method == "GET"
    assert timeout == backend_proxy.STANDARD_TIMEOUT_SECONDS
    assert fake_ec2.filters[-1] == {
        "Name": "instance-state-name",
        "Values": ["running"],
    }


def test_health_route_is_forwarded_to_fastapi(monkeypatch) -> None:
    monkeypatch.setattr(backend_proxy, "ec2", FakeEC2())
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr(backend_proxy, "urlopen", fake_urlopen)

    response = backend_proxy.lambda_handler(_event("GET", "/health"), None)

    assert response["statusCode"] == 200
    assert requests[0].full_url == "http://203.0.113.10:80/health"


def test_analysis_post_is_forwarded_without_short_api_gateway_timeout(monkeypatch) -> None:
    monkeypatch.setattr(backend_proxy, "ec2", FakeEC2())
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(backend_proxy, "urlopen", fake_urlopen)

    response = backend_proxy.lambda_handler(
        _event("POST", "/analyze", body='{"repo_url":"https://github.com/example/repo"}'),
        None,
    )

    request, timeout = requests[0]
    assert response["statusCode"] == 200
    assert request.method == "POST"
    assert request.data == b'{"repo_url":"https://github.com/example/repo"}'
    assert timeout == backend_proxy.ANALYSIS_TIMEOUT_SECONDS


def test_repository_routes_are_forwarded_to_fastapi(monkeypatch) -> None:
    monkeypatch.setattr(backend_proxy, "ec2", FakeEC2())
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr(backend_proxy, "urlopen", fake_urlopen)

    response = backend_proxy.lambda_handler(
        _event("GET", "/api/repositories/42"),
        None,
    )

    assert response["statusCode"] == 200
    assert requests[0].full_url == "http://203.0.113.10:80/api/repositories/42"


def test_repository_collection_path_is_forwarded_to_fastapi(monkeypatch) -> None:
    monkeypatch.setattr(backend_proxy, "ec2", FakeEC2())
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr(backend_proxy, "urlopen", fake_urlopen)

    response = backend_proxy.lambda_handler(
        _event("GET", "/api/repositories"),
        None,
    )

    assert response["statusCode"] == 200
    assert requests[0].full_url == "http://203.0.113.10:80/api/repositories"


def test_repository_history_path_is_forwarded_to_fastapi_with_pagination(monkeypatch) -> None:
    monkeypatch.setattr(backend_proxy, "ec2", FakeEC2())
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr(backend_proxy, "urlopen", fake_urlopen)

    response = backend_proxy.lambda_handler(
        _event("GET", "/api/repositories/history", "offset=0&limit=20"),
        None,
    )

    assert response["statusCode"] == 200
    assert requests[0].method == "GET"
    assert requests[0].full_url == "http://203.0.113.10:80/api/repositories/history?offset=0&limit=20"


def test_unknown_route_is_rejected_without_discovering_instance(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Unknown paths must not query EC2.")

    monkeypatch.setattr(backend_proxy, "ec2", type("NoEC2", (), {
        "describe_instances": fail_if_called,
    })())

    response = backend_proxy.lambda_handler(_event("GET", "/demo/stop"), None)

    assert response["statusCode"] == 404


def test_missing_running_instance_returns_service_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(backend_proxy, "ec2", FakeEC2(public_ip=None))

    response = backend_proxy.lambda_handler(_event("GET", "/health"), None)

    assert response["statusCode"] == 503
