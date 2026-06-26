"""测试对联评鉴 v4.3.0"""

import os
import pytest

from openprom.services.couplet_scorer import CoupletScorer
from openprom.utils.env_config import get_api_key


@pytest.mark.skipif(not os.getenv("OPENPROM_API_KEY"), reason="需要 OPENPROM_API_KEY 环境变量")
def test_couplet_scoring():
    """测试对联评分（需要真实 API Key）"""
    api_key = get_api_key()
    assert api_key, "API key is required"

    scorer = CoupletScorer()
    result = scorer.analyze("几孤风月", "屡变星霜")

    assert result.total_score >= 0, "总分不应为负数"
    assert result.total_score <= 100, "总分不应超过 100"
    assert result.grade in ["优秀", "良好", "及格", "不合格"], f"未知等级: {result.grade}"
    assert 0 <= result.formal_score <= 1, "formal_score 应在 0-1 之间"
    assert result.comments is not None, "评语不应为空"
