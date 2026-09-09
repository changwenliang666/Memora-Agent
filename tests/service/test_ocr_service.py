from app.service.ocr_service import figure_vision_text


def test_figure_vision_text_skips_exact_skip() -> None:
    assert figure_vision_text("SKIP") is None
    assert figure_vision_text("skip") is None
    assert figure_vision_text("  Skip  ") is None
    assert figure_vision_text("") is None
    assert figure_vision_text(None) is None


def test_figure_vision_text_keeps_skip_with_extra_text() -> None:
    assert figure_vision_text("SKIP 这是 logo") == "SKIP 这是 logo"
    assert figure_vision_text("图中有一只猫") == "图中有一只猫"
