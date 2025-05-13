from app.chain.history import HistorySerializer
from langchain.schema import HumanMessage, AIMessage


def test_history_serializer_mixed_entries():
    ser = HistorySerializer()
    raw = [
        {"human": "Hello"},          # only human
        {"ai": "Hi there!"},         # only ai
        {"human": "How are you?", "ai": "Fine"},  # both
    ]

    out = ser({"chat_history": raw})

    # Length == number of non-empty entries (3 human + 2 ai)
    # assert len(out) == 5
    # 2 human + 2 ai
    assert len(out) == 4
    assert isinstance(out[0], HumanMessage)
    assert isinstance(out[1], AIMessage)
    assert isinstance(out[-1], AIMessage)


def test_history_serializer_empty_history():
    ser = HistorySerializer()
    assert ser({}) == []
