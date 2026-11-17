"""Ask TrialFlow assistant: scope, tools, the tool loop, and the endpoint. A fake client stands in
for Claude, so these tests need no API key and make no network calls."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from app import models as m
from app import schemas as s
from app.enums import ActivationStatus, UserRole
from app.main import app
from app.services import assistant
from app.services import assistant_tools as tools
from app.services.assistant_tools import Scope, load_world
from conftest import AS_OF
from sqlalchemy import select

NOW = datetime.now(UTC)


# ---------- A scripted stand-in for anthropic.Anthropic ----------


def tool_use(name: str, args: dict, id_: str = "tu_1"):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=args)


def final(text: str, ids: list[int], follow: list[str] | None = None):
    payload = {"text": text, "trial_site_ids": ids, "follow": follow or []}
    return SimpleNamespace(type="text", text=json.dumps(payload))


class FakeClient:
    """Returns scripted responses in order and records every request."""

    def __init__(self, *turns):
        self.turns = list(turns)  # each turn: (stop_reason, [blocks])
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def with_options(self, **_):
        return self

    def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        stop, content = self.turns.pop(0) if self.turns else ("tool_use", [tool_use("portfolio_summary", {})])
        usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0)
        return SimpleNamespace(stop_reason=stop, content=content, usage=usage)


@pytest.fixture()
def world(seeded):
    return load_world(seeded, Scope(UserRole.startup_manager), AS_OF, NOW)


def _site_staff(seeded):
    """A site-staff user whose site has a tracked trial site."""
    for user in seeded.scalars(select(m.User).where(m.User.site_id.is_not(None))):
        if load_world(seeded, Scope(user.role, user.site_id), AS_OF, NOW):
            return user
    pytest.fail("no site staff user with a tracked trial site in the seed")


# ---------- Scope ----------


def test_sponsor_sees_every_tracked_trial_site(seeded, world):
    tracked = seeded.scalars(
        select(m.TrialSite).where(
            m.TrialSite.activation_status.in_(
                [ActivationStatus.in_startup, ActivationStatus.on_hold, ActivationStatus.activated]
            )
        )
    ).all()
    assert {d.id for d in world} == {ts.id for ts in tracked}
    assert len(world) > 1


def test_site_staff_see_only_their_site(seeded, world):
    user = _site_staff(seeded)
    mine = load_world(seeded, Scope(user.role, user.site_id), AS_OF, NOW)
    assert mine and all(d.site.id == user.site_id for d in mine)
    assert len(mine) < len(world)
    assert load_world(seeded, Scope(UserRole.contracts, None), AS_OF, NOW) == []


def test_tools_cannot_reach_out_of_scope_sites(seeded, world):
    user = _site_staff(seeded)
    mine = load_world(seeded, Scope(user.role, user.site_id), AS_OF, NOW)
    other = next(d for d in world if d.site.id != user.site_id)
    run = tools.run_tool("get_trial_site", {"trial_site_id": other.id}, mine, AS_OF)
    assert run.is_error and run.trial_site_ids == set()
    listed = tools.run_tool("list_trial_sites", {}, mine, AS_OF)
    assert listed.trial_site_ids == {d.id for d in mine}


# ---------- Tools ----------


def test_tool_results_carry_no_emails(world):
    out = [tools.run_tool(name, {}, world, AS_OF).result for name in ("portfolio_summary", "list_trial_sites")]
    out.append(tools.run_tool("open_tasks", {"limit": 50}, world, AS_OF).result)
    out += [tools.run_tool("get_trial_site", {"trial_site_id": d.id}, world, AS_OF).result for d in world]
    dumped = json.dumps(out, default=str)
    assert "@" not in dumped and "email" not in dumped


def test_open_tasks_filters(world):
    urgent = tools.run_tool("open_tasks", {"kind": "urgent", "limit": 50}, world, AS_OF).result
    assert urgent["tasks"] and all(t["kind"] in ("blocked", "overdue", "due_soon") for t in urgent["tasks"])
    owner = urgent["tasks"][0]["owner"]["name"]
    theirs = tools.run_tool("open_tasks", {"owner_name": owner.split()[0].lower()}, world, AS_OF).result
    assert theirs["total"] >= 1 and all(owner.split()[0] in t["owner"]["name"] for t in theirs["tasks"])
    capped = tools.run_tool("open_tasks", {"limit": 2}, world, AS_OF).result
    assert capped["shown"] == 2 and len(capped["tasks"]) == 2


def test_list_trial_sites_query_and_health(world):
    target = world[0]
    found = tools.run_tool("list_trial_sites", {"query": target.site.name[:12]}, world, AS_OF)
    assert target.id in found.trial_site_ids
    blocked = tools.run_tool("list_trial_sites", {"health": "blocked"}, world, AS_OF).result
    assert all(r["health"] == "blocked" for r in blocked["trial_sites"])


def test_bad_tool_calls_become_error_results(world):
    assert tools.run_tool("delete_everything", {}, world, AS_OF).is_error
    assert tools.run_tool("open_tasks", {"nope": 1}, world, AS_OF).is_error


# ---------- The loop ----------


def test_answer_links_only_sites_the_tools_returned(world):
    seen = world[0]
    client = FakeClient(
        ("tool_use", [tool_use("get_trial_site", {"trial_site_id": seen.id})]),
        ("end_turn", [final("IRB approval is holding it up.", [seen.id, 999_999], ["Who owns it?"])]),
    )
    answer = assistant.ask(client, "What's holding up this site?", [], world, AS_OF)
    assert answer.text == "IRB approval is holding it up."
    assert [link.href for link in answer.links] == [f"/sites/{seen.id}"]
    assert answer.follow == ["Who owns it?"] and answer.source == "claude"
    # The tool result went back to the model as a tool_result for the right call.
    results = client.calls[1]["messages"][-1]["content"]
    assert results[0]["type"] == "tool_result" and results[0]["tool_use_id"] == "tu_1"
    assert json.loads(results[0]["content"])["trial_site_id"] == seen.id


def test_request_settings(world):
    client = FakeClient(("end_turn", [final("Hi.", [])]))
    assistant.ask(client, "hello", [], world, AS_OF)
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["effort"] == "low"
    assert call["output_config"]["format"]["schema"] == assistant.ANSWER_SCHEMA
    assert call["fallbacks"] == "default" and call["betas"] == [assistant.FALLBACK_BETA]
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "tool_choice" not in call  # forced tool use is a 400 on Opus 5.5
    assert all(t["strict"] for t in call["tools"])


def test_history_is_merged_into_alternating_turns(world):
    client = FakeClient(("end_turn", [final("Nadia.", [])]))
    history = [
        s.AskTurn(role="assistant", text="Ask me anything."),  # dropped: must start with the user
        s.AskTurn(role="user", text="What's blocked?"),
        s.AskTurn(role="assistant", text="IRB approval at Ironwood."),
    ]
    assistant.ask(client, "Who owns it?", history, world, AS_OF)
    msgs = client.calls[0]["messages"]
    assert [x["role"] for x in msgs] == ["user", "assistant", "user"]
    assert msgs[-1]["content"].endswith("Who owns it?") and AS_OF.isoformat() in msgs[-1]["content"]


@pytest.mark.parametrize(
    "turns",
    [
        [("refusal", [])],
        [("max_tokens", [])],
        [("end_turn", [SimpleNamespace(type="text", text="not json")])],
        [],  # never stops calling tools: hits the round limit
    ],
)
def test_failures_raise_unavailable(world, turns):
    with pytest.raises(assistant.AssistantUnavailable):
        assistant.ask(FakeClient(*turns), "What's late?", [], world, AS_OF)


def test_round_limit(world):
    client = FakeClient()
    with pytest.raises(assistant.AssistantUnavailable):
        assistant.ask(client, "loop forever", [], world, AS_OF)
    assert len(client.calls) == assistant.MAX_ROUNDS


# ---------- Endpoint ----------

BODY = {"question": "What should I chase today?", "role": "startup_manager"}


def test_endpoint_without_key_is_503(client):
    app.dependency_overrides[assistant.get_client] = lambda: None
    r = client.post("/assistant/ask", json=BODY)
    assert r.status_code == 503 and r.json()["code"] == "assistant_unavailable"


def test_endpoint_answers_in_the_ask_contract(client, world):
    fake = FakeClient(
        ("tool_use", [tool_use("portfolio_summary", {})]),
        ("end_turn", [final("Start with IRB approval at Ironwood.", [world[0].id], ["Which sites are blocked?"])]),
    )
    app.dependency_overrides[assistant.get_client] = lambda: fake
    r = client.post("/assistant/ask", json=BODY)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"text", "links", "follow", "source"}
    assert body["text"] == "Start with IRB approval at Ironwood."


def test_endpoint_scopes_site_staff(client, seeded):
    user = _site_staff(seeded)
    fake = FakeClient(("tool_use", [tool_use("list_trial_sites", {})]), ("end_turn", [final("Yours.", [])]))
    app.dependency_overrides[assistant.get_client] = lambda: fake
    r = client.post("/assistant/ask", json={**BODY, "role": user.role.value, "site_id": user.site_id})
    assert r.status_code == 200
    listed = json.loads(fake.calls[1]["messages"][-1]["content"][0]["content"])
    assert listed["count"] >= 1
    assert {row["trial_site_id"] for row in listed["trial_sites"]} == {
        d.id for d in load_world(seeded, Scope(user.role, user.site_id), AS_OF, NOW)
    }


def test_endpoint_validates_input(client):
    app.dependency_overrides[assistant.get_client] = lambda: FakeClient()
    assert client.post("/assistant/ask", json={**BODY, "question": "x" * 301}).status_code == 422
    assert client.post("/assistant/ask", json={**BODY, "question": ""}).status_code == 422
    r = client.post("/assistant/ask", json={**BODY, "history": [{"role": "user", "text": "hi"}] * 11})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
