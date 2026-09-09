from app.service.rag_service import RagService
from app.service.text_split import split_ingest_text, split_markdown, split_plain


def _html_table_over_500() -> str:
    rows = "".join(f"<tr><td>row-{index}-{'内容' * 12}</td></tr>" for index in range(25))
    table = f"<table>{rows}</table>"
    assert len(table) > 500
    return table


def test_html_table_stays_in_one_chunk() -> None:
    table = _html_table_over_500()
    text = f"开场说明。\n\n{table}\n\n结尾说明。"
    docs = split_markdown(text, "kb/notes.md", "notes.md")

    matching = [doc for doc in docs if "<table>" in doc.page_content]
    assert len(matching) == 1
    assert table in matching[0].page_content
    assert matching[0].page_content.count("<table>") == 1
    assert matching[0].page_content.count("</table>") == 1
    assert all("<tr>" not in doc.page_content or table in doc.page_content for doc in docs)


def test_fenced_code_stays_in_one_chunk() -> None:
    fence = "```js\n# install deps\nconsole.log('hello world');\nfoo(); bar();\n```"
    text = f"## 示例\n\n{fence}\n\n说明文字。"
    docs = split_markdown(text, "kb/notes.md", "notes.md")

    matching = [doc for doc in docs if "console.log" in doc.page_content]
    assert len(matching) == 1
    content = matching[0].page_content
    assert "```js" in content
    assert content.count("```") >= 2
    assert "# install deps" in content
    assert "foo(); bar();" in content
    assert matching[0].metadata["h2"] == "示例"
    assert matching[0].metadata["source"] == "kb/notes.md"
    assert matching[0].metadata["filename"] == "notes.md"


def test_pipe_table_stays_in_one_chunk() -> None:
    table = "| 姓名 | 职级 |\n| --- | --- |\n| 张三 | P6 |\n| 李四 | P7 |"
    docs = split_markdown(f"前言\n\n{table}\n\n后记", "kb/notes.md", "notes.md")

    matching = [doc for doc in docs if "| 张三 | P6 |" in doc.page_content]
    assert len(matching) == 1
    assert "| 姓名 | 职级 |" in matching[0].page_content
    assert "| 李四 | P7 |" in matching[0].page_content


def test_hash_inside_fence_is_not_a_heading() -> None:
    text = "# 正题\n\n```bash\n# install\nnpm install\n```\n"
    docs = split_markdown(text, "kb/notes.md", "notes.md")

    assert all(doc.metadata.get("h1") == "正题" for doc in docs)
    assert not any(doc.metadata.get("h1") == "install" for doc in docs)
    fence_docs = [doc for doc in docs if "npm install" in doc.page_content]
    assert len(fence_docs) == 1
    assert "# install" in fence_docs[0].page_content


def test_heading_path_survives_prose_split() -> None:
    body = "这是一段说明。" * 80
    assert len(body) > 500
    text = f"## 考核制度\n\n{body}"
    docs = split_markdown(text, "kb/notes.md", "notes.md")

    assert len(docs) > 1
    assert all(doc.metadata.get("h2") == "考核制度" for doc in docs)
    assert all(doc.metadata["source"] == "kb/notes.md" for doc in docs)


def test_plain_txt_does_not_split_on_hash_headings() -> None:
    text = "# not a heading\n" + ("段落内容。" * 80)
    docs = split_plain(text, "kb/notes.txt", "notes.txt")

    assert docs
    assert all("h1" not in doc.metadata for doc in docs)
    assert any("# not a heading" in doc.page_content for doc in docs)
    assert all(doc.metadata["filename"] == "notes.txt" for doc in docs)


def test_split_ingest_text_routes_by_suffix() -> None:
    fence = "```js\nconsole.log(1);\n```"
    markdown_text = f"前言\n\n{fence}\n"
    markdown_docs = split_ingest_text(markdown_text, "kb/a.md", "a.md")
    pdf_docs = split_ingest_text(markdown_text, "kb/a.pdf", "a.pdf")
    txt_docs = split_ingest_text("# not a heading\n" + ("字" * 600), "kb/a.txt", "a.txt")

    assert any(
        "```js" in doc.page_content and doc.page_content.count("```") >= 2
        for doc in markdown_docs
    )
    assert any(
        "```js" in doc.page_content and doc.page_content.count("```") >= 2
        for doc in pdf_docs
    )
    assert all("h1" not in doc.metadata for doc in txt_docs)


def test_rag_service_split_text_uses_suffix() -> None:
    table = _html_table_over_500()
    md_docs = RagService.split_text(f"前\n\n{table}\n\n后", "kb/a.md", "notes.md")
    pdf_docs = RagService.split_text(f"前\n\n{table}\n\n后", "kb/a.pdf", "notes.pdf")
    txt = "# not a heading\n" + ("段落内容。" * 80)
    txt_docs = RagService.split_text(txt, "kb/a.txt", "notes.txt")
    png_docs = RagService.split_text(txt, "kb/a.png", "photo.png")

    assert any(table in doc.page_content for doc in md_docs)
    assert any(table in doc.page_content for doc in pdf_docs)
    assert all("h1" not in doc.metadata for doc in txt_docs)
    assert all("h1" not in doc.metadata for doc in png_docs)
    assert any("# not a heading" in doc.page_content for doc in txt_docs)
