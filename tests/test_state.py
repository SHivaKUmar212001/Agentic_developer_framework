from __future__ import annotations

from forge.core.state import SharedState


def test_get_relevant_repo_files_prefers_matching_paths(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text("def login():\n    return True\n", encoding="utf-8")
    (tmp_path / "src" / "db.py").write_text("def connect():\n    return None\n", encoding="utf-8")

    state = SharedState(mode="fix", repo_path=str(tmp_path))
    relevant = state.get_relevant_repo_files("fix login auth bug", max_files=1)

    assert relevant
    assert relevant[0][0] == "src/auth.py"
