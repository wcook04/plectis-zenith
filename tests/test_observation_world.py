"""Scientific boundaries and actual native-software behavior of the assay."""
import json

import pytest

from research.observation_world import (
    GOALS, WorldConfig, cases, compatible, discovery_sequences, expected,
    make_dataset, observe, task_sequences, task_spec, world,
)


def put(key="a", value=2, connection="main"):
    return {"op": "put", "key": key, "value": value, "connection": connection}


def config(conflict="ignore", trigger=False, counter="main_total"):
    return WorldConfig("opaque-source", conflict, trigger, counter)


def test_native_trigger_and_conflict_effects():
    sequence = [put(), put(value=5)]
    ignored = observe(config("ignore", True), sequence)["observed"]
    replaced = observe(config("replace", True), sequence)["observed"]
    updated = observe(config("upsert", True), sequence)["observed"]
    assert ignored == {"channel": 2, "committed_count": 1, "committed_sum": 2}
    assert replaced == {"channel": 4, "committed_count": 1, "committed_sum": 5}
    assert updated == {"channel": 3, "committed_count": 1, "committed_sum": 5}


def test_rollback_counter_is_not_committed_work():
    actions = [{"op": "begin"}, put(), {"op": "rollback"}]
    assert observe(config(trigger=True), actions)["observed"] == {
        "channel": 2, "committed_count": 0, "committed_sum": 0}
    assert observe(config(counter="main_direct"), actions)["observed"]["channel"] == 1


def test_noop_update_and_second_connection_are_distinct():
    noop = [put(), {"op": "update", "key": "a", "value": 2}]
    assert observe(config(), noop)["observed"] == {"channel": 2, "committed_count": 1, "committed_sum": 2}
    other = [put(connection="other")]
    assert observe(config(), other)["observed"] == {"channel": 0, "committed_count": 1, "committed_sum": 2}
    assert observe(config(counter="all_total"), other)["observed"]["channel"] == 1


def test_open_transaction_uses_independent_committed_reader():
    assert observe(config(), [{"op": "begin"}, put()])["observed"] == {
        "channel": 1, "committed_count": 0, "committed_sum": 0}


def test_equal_visible_histories_can_require_different_future_answers():
    a, b = config("ignore"), config("replace")
    history = [observe(a, [put()])]
    assert history[0]["observed"] == observe(b, [put()])["observed"]
    future = [put(), put(value=5)]
    assert observe(a, future)["observed"]["committed_sum"] == 2
    assert observe(b, future)["observed"]["committed_sum"] == 5
    assert expected(a, history, future, "committed_sum") == {"value": None, "unresolved": True}
    assert expected(a, history, future, "committed_count") == {"value": 1, "unresolved": False}


def test_identification_preserves_answerable_goals_without_identifying_all_flags():
    cfg = config("replace", False, "main_direct")
    history = [observe(cfg, a) for a in discovery_sequences()]
    assert len(compatible(cfg, history)) > 1  # Invisible insertion instrumentation can remain ambiguous.
    for sequence in task_sequences(81):
        for goal in GOALS:
            assert expected(cfg, history, sequence, goal) == {
                "value": observe(cfg, sequence)["observed"][goal], "unresolved": False}


def test_private_modes_and_reference_targets_do_not_enter_query_context():
    cfg = world(51013)
    history = [observe(cfg, actions) for actions in discovery_sequences()[:3]]
    pairs = cases(cfg, history, task_sequences(13), goals=("channel",))
    for case, key in pairs:
        assert set(case) == {"id", "source_id", "actions", "goal", "documentation", "tables"}
        assert set(key) == {"value", "unresolved"}
        assert case["tables"] == {"history": history}
        assert "observed" not in case
        assert "private" not in case and "config" not in case and "seed" not in case
    assert "main_direct" not in task_spec() and "insert_trigger" not in task_spec()


def test_public_support_contract_discloses_all_evaluator_possibilities():
    description = task_spec()
    for phrase in ('18-member family', 'INSERT OR IGNORE', 'INSERT OR REPLACE',
                   'ON CONFLICT(id) DO UPDATE', 'AFTER INSERT', 'main connection changes()',
                   'main total_changes plus other total_changes', 'every member'):
        assert phrase in description
    assert 'actual combination is private' in description


def test_custody_and_mutation_checks():
    cfg = config()
    receipt = observe(cfg, [put()])
    tampered = json.loads(json.dumps(receipt))
    tampered["observed"]["channel"] += 1
    with pytest.raises(ValueError, match="content changed"):
        compatible(cfg, [tampered])
    with pytest.raises(ValueError, match="another source"):
        compatible(WorldConfig("different", "ignore", False, "main_total"), [receipt])
    pairs = cases(cfg, [receipt], [[put()]])
    pairs[0][0]["tables"]["history"][0]["observed"]["channel"] = 99
    assert receipt["observed"]["channel"] == 1


def test_structural_partition_and_marginal_balance():
    dataset = make_dataset(77, 12)
    assert set(dataset) == {"public", "private"}
    assert dataset["public"]["checkpoint_prefixes"] == [3, 6, 9]
    assert len(dataset["public"]["streams"]) == 12
    settings = list(dataset["private"]["configs"].values())
    for field, choices in [("conflict", ("ignore", "replace", "upsert")),
                           ("counter", ("main_direct", "main_total", "all_total")),
                           ("insert_trigger", (False, True))]:
        assert len({sum(row[field] == choice for row in settings) for choice in choices}) == 1
    for stream in dataset["public"]["streams"]:
        partitions = stream["partitions"]
        encoded = [{json.dumps(a, sort_keys=True) for a in partitions[name]} for name in ("learn", "challenge", "eval")]
        assert all(not encoded[i] & encoded[j] for i in range(3) for j in range(i))
        assert len(partitions["eval"]) == 16
        for sequences in partitions.values():
            for sequence in sequences:
                observe(WorldConfig(**dataset["private"]["configs"][stream["source_id"]]), sequence)


@pytest.mark.parametrize("actions", [
    [{"op": "commit"}], [{"op": "begin"}, {"op": "begin"}],
    [{"op": "begin"}, put(connection="other")],
    [put(value=-1)], [put(value=True)], [{"op": "put", "key": "a", "value": 2, "sql": "SELECT 1"}],
    [{"op": "attach"}], [put()] * 33,
])
def test_invalid_or_unbounded_actions_are_rejected(actions):
    with pytest.raises(ValueError):
        observe(config(), actions)
