#!/usr/bin/env python3
"""Extract visible assistant targets without flattening native tool context."""

import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from milk_v2 import eval_plan, summary
from milk_v2.state import atomic_json, redact
from milk_v2.store import StoreError, open_store, settings_from_environment

VERSION = "milk.native-assistant-example.v1"


class Unsupported(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Unsupported(reason)


def content(value):
    if value is None or isinstance(value, str):
        return value
    require(isinstance(value, list), "unsupported_content")
    parts = []
    for item in value:
        require(isinstance(item, dict) and item.get("type") in {"text", "input_text", "output_text"}
                and isinstance(item.get("text"), str) and not item.get("annotations"), "multimodal_or_annotated_content")
        parts.append({"type": "text", "text": item["text"]})
    return parts


def call(identifier, function):
    require(isinstance(identifier, str) and bool(identifier) and isinstance(function, dict), "invalid_tool_call")
    require(isinstance(function.get("name"), str) and bool(function["name"])
            and isinstance(function.get("arguments"), str), "invalid_tool_call")
    try:
        arguments = json.loads(function["arguments"])
    except ValueError:
        raise Unsupported("invalid_tool_arguments") from None
    require(isinstance(arguments, dict), "nonobject_tool_arguments")
    return {"id": identifier, "type": "function", "function": {"name": function["name"], "arguments": function["arguments"]}}


def messages(items, mode, omissions):
    require(isinstance(items, list), "missing_message_history")
    result = []
    for item in items:
        require(isinstance(item, dict), "invalid_message")
        kind = item.get("type")
        if mode == "responses" and kind == "reasoning":
            omissions["reasoning_items"] += 1
            omissions["encrypted_reasoning_items"] += bool(item.get("encrypted_content"))
            continue
        if mode == "responses" and kind == "function_call":
            require(item.get("status") in {None, "completed"}, "incomplete_tool_call")
            result.append({"role": "assistant", "content": None, "tool_calls": [call(item.get("call_id"), item)]})
            continue
        if mode == "responses" and kind == "function_call_output":
            require(isinstance(item.get("call_id"), str) and isinstance(item.get("output"), str), "unsupported_tool_output")
            result.append({"role": "tool", "tool_call_id": item["call_id"], "content": item["output"]})
            continue
        require(kind in {None, "message"}, "unknown_response_item")
        require(not item.get("encrypted_content"), "opaque_message_content")
        role = item.get("role")
        require(role in {"system", "developer", "user", "assistant", "tool"}, "unknown_message_role")
        require(not any(item.get(key) for key in ("refusal", "audio", "function_call", "annotations")), "unsupported_message_semantics")
        message = {"role": role, "content": content(item.get("content"))}
        if item.get("reasoning_content"):
            omissions["reasoning_items"] += 1
        if item.get("tool_calls"):
            require(role == "assistant" and isinstance(item["tool_calls"], list), "invalid_tool_calls")
            message["tool_calls"] = []
            for entry in item["tool_calls"]:
                require(isinstance(entry, dict) and entry.get("type") == "function", "unsupported_tool_call")
                message["tool_calls"].append(call(entry.get("id"), entry.get("function")))
        if role == "tool":
            require(isinstance(item.get("tool_call_id"), str) and isinstance(message["content"], str), "unsupported_tool_output")
            message["tool_call_id"] = item["tool_call_id"]
        require(message["content"] is not None or bool(message.get("tool_calls")), "missing_visible_message")
        result.append(message)
    return result


def tool_sequence(context, targets, tools):
    names = {tool["function"]["name"] for tool in tools}
    seen, pending = set(), set()
    for index, message in enumerate(context + targets):
        if index == len(context):
            require(not pending, "historical_tool_results_missing")
        if index >= len(context):
            require(message["role"] == "assistant", "nonassistant_target")
        if message["role"] == "tool":
            identifier = message["tool_call_id"]
            require(identifier in pending, "orphan_or_duplicate_tool_result")
            pending.remove(identifier)
        else:
            calls = message.get("tool_calls", [])
            require(not pending or (message["role"] == "assistant" and bool(calls)), "interrupted_tool_sequence")
            for entry in calls:
                require(entry["id"] not in seen and entry["function"]["name"] in names, "duplicate_or_unknown_tool_call")
                seen.add(entry["id"])
                pending.add(entry["id"])


def decode(envelope, request, response):
    require(not envelope.get("streaming"), "streaming_not_supported")
    require(isinstance(request, dict) and isinstance(response, dict), "invalid_protocol_body")
    require(not request.get("previous_response_id") and not request.get("conversation"), "server_side_history_missing")
    mode = envelope.get("endpoint")
    require(mode in {"responses", "chat_completions"}, "unsupported_endpoint")
    tools = []
    require(isinstance(request.get("tools", []), list), "invalid_tool_definitions")
    for tool in request.get("tools", []):
        require(isinstance(tool, dict) and tool.get("type") == "function", "unsupported_tool_definition")
        function = tool if mode == "responses" else tool.get("function")
        require(isinstance(function, dict) and isinstance(function.get("name"), str)
                and bool(function["name"]) and isinstance(function.get("parameters"), dict), "invalid_tool_definition")
        tools.append({"type": "function", "function": {key: function[key] for key in ("name", "description", "parameters", "strict") if key in function}})
    require(len({tool["function"]["name"] for tool in tools}) == len(tools), "duplicate_tool_definition")
    omissions = {"reasoning_items": 0, "encrypted_reasoning_items": 0}
    if mode == "responses":
        require(response.get("status") == "completed", "incomplete_assistant_turn")
        inputs = request.get("input", [])
        if isinstance(inputs, str):
            inputs = [{"role": "user", "content": inputs}]
        context = messages(inputs, mode, omissions)
        if request.get("instructions"):
            require(isinstance(request["instructions"], str), "unsupported_instructions")
            context.insert(0, {"role": "system", "content": request["instructions"]})
        targets = messages(response.get("output"), mode, omissions)
    else:
        choices = response.get("choices")
        require(isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict), "multiple_or_missing_choices")
        require(choices[0].get("finish_reason") in {"stop", "tool_calls"}, "incomplete_assistant_turn")
        context = messages(request.get("messages"), mode, omissions)
        targets = messages([choices[0].get("message")], mode, omissions)
    require(bool(context) and bool(targets), "no_visible_assistant_target")
    require(any(message.get("tool_calls") or (bool(message["content"]) if isinstance(message["content"], str)
                else any(part["text"] for part in message["content"] or [])) for message in targets), "no_visible_assistant_target")
    tool_sequence(context, targets, tools)
    return {"messages": context, "tools": tools, "next_assistant_targets": targets,
            "training_target": "visible_assistant_only", "omitted_reasoning": bool(omissions["reasoning_items"]), "omissions": omissions}


def main():
    if sys.argv[1:] not in ([], ["run"]):
        raise ValueError("usage: native_capture.py [run]")
    settings = settings_from_environment()
    key, expected = os.environ["MILK_NATIVE_CAPTURE_KEY"], os.environ["MILK_NATIVE_CAPTURE_SHA256"]
    if not key.startswith(settings.scope_prefix + "c/") or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("capture key or digest is outside the configured contract")
    stored, envelope, request_body, response_body = summary.read_capture(open_store(settings), settings, key)
    if summary.digest(stored.body) != expected:
        raise ValueError("capture object digest differs")
    source = {"scope_id": settings.scope_id, "profile": settings.profile, "capture_key": key,
              "object_sha256": expected, "request_sha256": summary.digest(request_body), "response_sha256": summary.digest(response_body),
              "content_sha256": summary.digest(request_body + b"\0" + response_body), "trajectory_id": envelope.get("trajectory_id"), "endpoint": envelope.get("endpoint")}
    group = eval_plan.source_group(source["request_sha256"], source["trajectory_id"], settings.scope_id)
    source.update(source_group_kind=group["kind"], source_group_sha256=group["sha256"], split=eval_plan.split_for_group(group["sha256"], group["kind"]))
    decoder_sha256 = summary.digest(Path(__file__).read_bytes())
    identity = summary.digest({"schema_version": VERSION, "source": source, "decoder_sha256": decoder_sha256})
    details = {"source": source, "decoder_sha256": decoder_sha256, "task_success": None, "training_ready": False}
    try:
        require(envelope.get("trajectory_id") is not None, "trajectory_id_missing")
        require(200 <= envelope["response"].get("status", 0) < 300, "upstream_failure")
        require(not envelope.get("streaming"), "streaming_not_supported")
        native = decode(envelope, summary._json(request_body, "request"), summary._json(response_body, "response"))
        state = Path(os.environ.get("MILK_MAN_STATE_DIR", str(Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "milk-man"))).expanduser().resolve()
        if state == ROOT or ROOT in state.parents:
            raise ValueError("native capture artifacts must stay outside the repository")
        path = state / "native-captures" / (identity + ".json")
        atomic_json(path, {"schema_version": VERSION, "source": source, "decoder_sha256": decoder_sha256, **native})
        details.update(supported=True, artifact_file=str(path), artifact_sha256=summary.digest(path.read_bytes()),
                       context_messages=len(native["messages"]), tools=len(native["tools"]), assistant_targets=len(native["next_assistant_targets"]),
                       target_tool_calls=sum(len(message.get("tool_calls", [])) for message in native["next_assistant_targets"]),
                       training_target=native["training_target"], omitted_reasoning=native["omitted_reasoning"], omissions=native["omissions"])
    except Unsupported as error:
        details.update(supported=False, reason=str(error))
    print(json.dumps({"state": "complete", "identity": identity, "inference_calls": 0, "provider_calls": 0, "details": details}, separators=(",", ":")))


if __name__ == "__main__":
    os.umask(0o077)
    try:
        main()
    except (KeyError, ValueError, OSError, StoreError) as error:
        print(json.dumps({"state": "failed", "identity": "native-capture", "inference_calls": 0, "provider_calls": 0, "error": redact(str(error))}, separators=(",", ":")))
        raise SystemExit(1)
