# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
from typing import Any, cast

import pytest

from agentex import Agentex, AsyncAgentex
from agentex.types import (
    Task,
    TaskListResponse,
    TaskRetrieveResponse,
    TaskQueryWorkflowResponse,
    TaskRetrieveByNameResponse,
)
from agentex.types.shared import DeleteResponse

from ..utils import assert_matches_type

base_url = os.environ.get("TEST_API_BASE_URL", "http://127.0.0.1:4010")


class TestTasks:
    parametrize = pytest.mark.parametrize("client", [False, True], indirect=True, ids=["loose", "strict"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_retrieve(self, client: Agentex) -> None:
        task = client.tasks.retrieve(
            task_id="task_id",
        )
        assert_matches_type(TaskRetrieveResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_retrieve_with_all_params(self, client: Agentex) -> None:
        task = client.tasks.retrieve(
            task_id="task_id",
            relationships=["agents"],
        )
        assert_matches_type(TaskRetrieveResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_retrieve(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.retrieve(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(TaskRetrieveResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_retrieve(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.retrieve(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(TaskRetrieveResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_retrieve(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            client.tasks.with_raw_response.retrieve(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_list(self, client: Agentex) -> None:
        task = client.tasks.list()
        assert_matches_type(TaskListResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_list_with_all_params(self, client: Agentex) -> None:
        task = client.tasks.list(
            agent_id="agent_id",
            agent_name="agent_name",
            limit=0,
            order_by="order_by",
            order_direction="order_direction",
            page_number=0,
            relationships=["agents"],
        )
        assert_matches_type(TaskListResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_list(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.list()

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(TaskListResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_list(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.list() as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(TaskListResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_delete(self, client: Agentex) -> None:
        task = client.tasks.delete(
            "task_id",
        )
        assert_matches_type(DeleteResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_delete(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.delete(
            "task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(DeleteResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_delete(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.delete(
            "task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(DeleteResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_delete(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            client.tasks.with_raw_response.delete(
                "",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_cancel(self, client: Agentex) -> None:
        task = client.tasks.cancel(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_cancel_with_all_params(self, client: Agentex) -> None:
        task = client.tasks.cancel(
            task_id="task_id",
            reason="reason",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_cancel(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.cancel(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_cancel(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.cancel(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_cancel(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            client.tasks.with_raw_response.cancel(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_complete(self, client: Agentex) -> None:
        task = client.tasks.complete(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_complete_with_all_params(self, client: Agentex) -> None:
        task = client.tasks.complete(
            task_id="task_id",
            reason="reason",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_complete(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.complete(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_complete(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.complete(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_complete(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            client.tasks.with_raw_response.complete(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_delete_by_name(self, client: Agentex) -> None:
        task = client.tasks.delete_by_name(
            "task_name",
        )
        assert_matches_type(DeleteResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_delete_by_name(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.delete_by_name(
            "task_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(DeleteResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_delete_by_name(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.delete_by_name(
            "task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(DeleteResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_delete_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            client.tasks.with_raw_response.delete_by_name(
                "",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_fail(self, client: Agentex) -> None:
        task = client.tasks.fail(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_fail_with_all_params(self, client: Agentex) -> None:
        task = client.tasks.fail(
            task_id="task_id",
            reason="reason",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_fail(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.fail(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_fail(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.fail(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_fail(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            client.tasks.with_raw_response.fail(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_query_workflow(self, client: Agentex) -> None:
        task = client.tasks.query_workflow(
            query_name="query_name",
            task_id="task_id",
        )
        assert_matches_type(TaskQueryWorkflowResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_query_workflow(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.query_workflow(
            query_name="query_name",
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(TaskQueryWorkflowResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_query_workflow(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.query_workflow(
            query_name="query_name",
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(TaskQueryWorkflowResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_query_workflow(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            client.tasks.with_raw_response.query_workflow(
                query_name="query_name",
                task_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `query_name` but received ''"):
            client.tasks.with_raw_response.query_workflow(
                query_name="",
                task_id="task_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_retrieve_by_name(self, client: Agentex) -> None:
        task = client.tasks.retrieve_by_name(
            task_name="task_name",
        )
        assert_matches_type(TaskRetrieveByNameResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_retrieve_by_name_with_all_params(self, client: Agentex) -> None:
        task = client.tasks.retrieve_by_name(
            task_name="task_name",
            relationships=["agents"],
        )
        assert_matches_type(TaskRetrieveByNameResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_retrieve_by_name(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.retrieve_by_name(
            task_name="task_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(TaskRetrieveByNameResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_retrieve_by_name(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.retrieve_by_name(
            task_name="task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(TaskRetrieveByNameResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_retrieve_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            client.tasks.with_raw_response.retrieve_by_name(
                task_name="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_stream_events(self, client: Agentex) -> None:
        task_stream = client.tasks.stream_events(
            "task_id",
        )
        task_stream.response.close()

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_stream_events(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.stream_events(
            "task_id",
        )

        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        stream = response.parse()
        stream.close()

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_stream_events(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.stream_events(
            "task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            stream = response.parse()
            stream.close()

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_stream_events(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            client.tasks.with_raw_response.stream_events(
                "",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_stream_events_by_name(self, client: Agentex) -> None:
        task_stream = client.tasks.stream_events_by_name(
            "task_name",
        )
        task_stream.response.close()

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_stream_events_by_name(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.stream_events_by_name(
            "task_name",
        )

        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        stream = response.parse()
        stream.close()

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_stream_events_by_name(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.stream_events_by_name(
            "task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            stream = response.parse()
            stream.close()

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_stream_events_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            client.tasks.with_raw_response.stream_events_by_name(
                "",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_terminate(self, client: Agentex) -> None:
        task = client.tasks.terminate(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_terminate_with_all_params(self, client: Agentex) -> None:
        task = client.tasks.terminate(
            task_id="task_id",
            reason="reason",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_terminate(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.terminate(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_terminate(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.terminate(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_terminate(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            client.tasks.with_raw_response.terminate(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_timeout(self, client: Agentex) -> None:
        task = client.tasks.timeout(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_timeout_with_all_params(self, client: Agentex) -> None:
        task = client.tasks.timeout(
            task_id="task_id",
            reason="reason",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_timeout(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.timeout(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_timeout(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.timeout(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_timeout(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            client.tasks.with_raw_response.timeout(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_update_by_id(self, client: Agentex) -> None:
        task = client.tasks.update_by_id(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_update_by_id_with_all_params(self, client: Agentex) -> None:
        task = client.tasks.update_by_id(
            task_id="task_id",
            task_metadata={"foo": "bar"},
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_update_by_id(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.update_by_id(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_update_by_id(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.update_by_id(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_update_by_id(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            client.tasks.with_raw_response.update_by_id(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_update_by_name(self, client: Agentex) -> None:
        task = client.tasks.update_by_name(
            task_name="task_name",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_method_update_by_name_with_all_params(self, client: Agentex) -> None:
        task = client.tasks.update_by_name(
            task_name="task_name",
            task_metadata={"foo": "bar"},
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_raw_response_update_by_name(self, client: Agentex) -> None:
        response = client.tasks.with_raw_response.update_by_name(
            task_name="task_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_streaming_response_update_by_name(self, client: Agentex) -> None:
        with client.tasks.with_streaming_response.update_by_name(
            task_name="task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    def test_path_params_update_by_name(self, client: Agentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            client.tasks.with_raw_response.update_by_name(
                task_name="",
            )


class TestAsyncTasks:
    parametrize = pytest.mark.parametrize(
        "async_client", [False, True, {"http_client": "aiohttp"}], indirect=True, ids=["loose", "strict", "aiohttp"]
    )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_retrieve(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.retrieve(
            task_id="task_id",
        )
        assert_matches_type(TaskRetrieveResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_retrieve_with_all_params(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.retrieve(
            task_id="task_id",
            relationships=["agents"],
        )
        assert_matches_type(TaskRetrieveResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_retrieve(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.retrieve(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(TaskRetrieveResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_retrieve(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.retrieve(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(TaskRetrieveResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_retrieve(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            await async_client.tasks.with_raw_response.retrieve(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_list(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.list()
        assert_matches_type(TaskListResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_list_with_all_params(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.list(
            agent_id="agent_id",
            agent_name="agent_name",
            limit=0,
            order_by="order_by",
            order_direction="order_direction",
            page_number=0,
            relationships=["agents"],
        )
        assert_matches_type(TaskListResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_list(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.list()

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(TaskListResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_list(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.list() as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(TaskListResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_delete(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.delete(
            "task_id",
        )
        assert_matches_type(DeleteResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_delete(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.delete(
            "task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(DeleteResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_delete(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.delete(
            "task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(DeleteResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_delete(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            await async_client.tasks.with_raw_response.delete(
                "",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_cancel(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.cancel(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_cancel_with_all_params(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.cancel(
            task_id="task_id",
            reason="reason",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_cancel(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.cancel(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_cancel(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.cancel(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_cancel(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            await async_client.tasks.with_raw_response.cancel(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_complete(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.complete(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_complete_with_all_params(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.complete(
            task_id="task_id",
            reason="reason",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_complete(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.complete(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_complete(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.complete(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_complete(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            await async_client.tasks.with_raw_response.complete(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_delete_by_name(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.delete_by_name(
            "task_name",
        )
        assert_matches_type(DeleteResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_delete_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.delete_by_name(
            "task_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(DeleteResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_delete_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.delete_by_name(
            "task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(DeleteResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_delete_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            await async_client.tasks.with_raw_response.delete_by_name(
                "",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_fail(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.fail(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_fail_with_all_params(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.fail(
            task_id="task_id",
            reason="reason",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_fail(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.fail(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_fail(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.fail(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_fail(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            await async_client.tasks.with_raw_response.fail(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_query_workflow(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.query_workflow(
            query_name="query_name",
            task_id="task_id",
        )
        assert_matches_type(TaskQueryWorkflowResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_query_workflow(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.query_workflow(
            query_name="query_name",
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(TaskQueryWorkflowResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_query_workflow(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.query_workflow(
            query_name="query_name",
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(TaskQueryWorkflowResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_query_workflow(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            await async_client.tasks.with_raw_response.query_workflow(
                query_name="query_name",
                task_id="",
            )

        with pytest.raises(ValueError, match=r"Expected a non-empty value for `query_name` but received ''"):
            await async_client.tasks.with_raw_response.query_workflow(
                query_name="",
                task_id="task_id",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.retrieve_by_name(
            task_name="task_name",
        )
        assert_matches_type(TaskRetrieveByNameResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_retrieve_by_name_with_all_params(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.retrieve_by_name(
            task_name="task_name",
            relationships=["agents"],
        )
        assert_matches_type(TaskRetrieveByNameResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.retrieve_by_name(
            task_name="task_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(TaskRetrieveByNameResponse, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.retrieve_by_name(
            task_name="task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(TaskRetrieveByNameResponse, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_retrieve_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            await async_client.tasks.with_raw_response.retrieve_by_name(
                task_name="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_stream_events(self, async_client: AsyncAgentex) -> None:
        task_stream = await async_client.tasks.stream_events(
            "task_id",
        )
        await task_stream.response.aclose()

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_stream_events(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.stream_events(
            "task_id",
        )

        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        stream = await response.parse()
        await stream.close()

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_stream_events(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.stream_events(
            "task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            stream = await response.parse()
            await stream.close()

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_stream_events(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            await async_client.tasks.with_raw_response.stream_events(
                "",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_stream_events_by_name(self, async_client: AsyncAgentex) -> None:
        task_stream = await async_client.tasks.stream_events_by_name(
            "task_name",
        )
        await task_stream.response.aclose()

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_stream_events_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.stream_events_by_name(
            "task_name",
        )

        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        stream = await response.parse()
        await stream.close()

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_stream_events_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.stream_events_by_name(
            "task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            stream = await response.parse()
            await stream.close()

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_stream_events_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            await async_client.tasks.with_raw_response.stream_events_by_name(
                "",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_terminate(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.terminate(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_terminate_with_all_params(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.terminate(
            task_id="task_id",
            reason="reason",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_terminate(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.terminate(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_terminate(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.terminate(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_terminate(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            await async_client.tasks.with_raw_response.terminate(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_timeout(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.timeout(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_timeout_with_all_params(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.timeout(
            task_id="task_id",
            reason="reason",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_timeout(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.timeout(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_timeout(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.timeout(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_timeout(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            await async_client.tasks.with_raw_response.timeout(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_update_by_id(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.update_by_id(
            task_id="task_id",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_update_by_id_with_all_params(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.update_by_id(
            task_id="task_id",
            task_metadata={"foo": "bar"},
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_update_by_id(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.update_by_id(
            task_id="task_id",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_update_by_id(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.update_by_id(
            task_id="task_id",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_update_by_id(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_id` but received ''"):
            await async_client.tasks.with_raw_response.update_by_id(
                task_id="",
            )

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_update_by_name(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.update_by_name(
            task_name="task_name",
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_method_update_by_name_with_all_params(self, async_client: AsyncAgentex) -> None:
        task = await async_client.tasks.update_by_name(
            task_name="task_name",
            task_metadata={"foo": "bar"},
        )
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_raw_response_update_by_name(self, async_client: AsyncAgentex) -> None:
        response = await async_client.tasks.with_raw_response.update_by_name(
            task_name="task_name",
        )

        assert response.is_closed is True
        assert response.http_request.headers.get("X-Stainless-Lang") == "python"
        task = await response.parse()
        assert_matches_type(Task, task, path=["response"])

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_streaming_response_update_by_name(self, async_client: AsyncAgentex) -> None:
        async with async_client.tasks.with_streaming_response.update_by_name(
            task_name="task_name",
        ) as response:
            assert not response.is_closed
            assert response.http_request.headers.get("X-Stainless-Lang") == "python"

            task = await response.parse()
            assert_matches_type(Task, task, path=["response"])

        assert cast(Any, response.is_closed) is True

    @pytest.mark.skip(reason="Mock server tests are disabled")
    @parametrize
    async def test_path_params_update_by_name(self, async_client: AsyncAgentex) -> None:
        with pytest.raises(ValueError, match=r"Expected a non-empty value for `task_name` but received ''"):
            await async_client.tasks.with_raw_response.update_by_name(
                task_name="",
            )
