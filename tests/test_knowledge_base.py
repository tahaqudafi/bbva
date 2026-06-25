"""
Unit tests for knowledge base loading and search.
Uses a temporary directory — no real files or APIs required.
"""

import tempfile
from pathlib import Path

import pytest

from knowledge_base import KnowledgeBase


@pytest.fixture()
def tmp_kb(tmp_path: Path) -> KnowledgeBase:
    """Return a KnowledgeBase pointed at a fresh empty temp directory."""
    return KnowledgeBase(tmp_path)


class TestLoading:
    def test_empty_dir_loads_without_error(self, tmp_kb: KnowledgeBase):
        tmp_kb.load()
        assert tmp_kb.is_empty is True

    def test_txt_file_loaded(self, tmp_path: Path):
        (tmp_path / "faq.txt").write_text("Our return policy is 30 days.")
        kb = KnowledgeBase(tmp_path)
        kb.load()
        assert not kb.is_empty
        assert "faq.txt" in kb.loaded_files

    def test_unsupported_files_ignored(self, tmp_path: Path):
        (tmp_path / "readme.md").write_text("# Docs")
        (tmp_path / "data.csv").write_text("col1,col2\n1,2")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        kb = KnowledgeBase(tmp_path)
        kb.load()
        assert kb.is_empty

    def test_empty_txt_file_produces_no_document(self, tmp_path: Path):
        (tmp_path / "empty.txt").write_text("   \n   ")
        kb = KnowledgeBase(tmp_path)
        kb.load()
        assert kb.is_empty

    def test_multiple_txt_files_all_loaded(self, tmp_path: Path):
        (tmp_path / "a.txt").write_text("Shipping takes 3–5 days.")
        (tmp_path / "b.txt").write_text("We accept Visa and Mastercard.")
        kb = KnowledgeBase(tmp_path)
        kb.load()
        assert len(kb.loaded_files) == 2


class TestSearch:
    def test_search_finds_relevant_content(self, tmp_path: Path):
        (tmp_path / "faq.txt").write_text(
            "Our return policy allows returns within 30 days of purchase with a receipt."
        )
        kb = KnowledgeBase(tmp_path)
        kb.load()
        result = kb.search("return policy")
        assert result is not None
        assert "return" in result.lower()

    def test_search_returns_none_for_empty_kb(self, tmp_kb: KnowledgeBase):
        tmp_kb.load()
        assert tmp_kb.search("anything") is None

    def test_search_returns_none_for_missing_content(self, tmp_path: Path):
        (tmp_path / "faq.txt").write_text("We sell widgets and gadgets.")
        kb = KnowledgeBase(tmp_path)
        kb.load()
        assert kb.search("xyzzy_nonexistent_topic_99999") is None

    def test_search_includes_source_name(self, tmp_path: Path):
        (tmp_path / "products.txt").write_text("We sell blue widgets for industrial use.")
        kb = KnowledgeBase(tmp_path)
        kb.load()
        result = kb.search("blue widgets")
        assert result is not None
        assert "products.txt" in result

    def test_search_across_multiple_documents(self, tmp_path: Path):
        (tmp_path / "shipping.txt").write_text("Shipping takes 3–5 business days.")
        (tmp_path / "returns.txt").write_text("Returns are accepted within 30 days.")
        kb = KnowledgeBase(tmp_path)
        kb.load()
        result = kb.search("shipping time")
        assert result is not None
        assert "shipping" in result.lower()


class TestChunking:
    def test_long_document_produces_multiple_chunks(self, tmp_path: Path):
        # Create text clearly longer than one chunk (600 chars)
        paras = ["Paragraph number " + str(i) + ". " + "Content. " * 30 for i in range(10)]
        (tmp_path / "long.txt").write_text("\n\n".join(paras))
        kb = KnowledgeBase(tmp_path)
        kb.load()
        # Confirm document was loaded
        assert not kb.is_empty
        doc = kb._documents[0]
        assert len(doc["chunks"]) > 1