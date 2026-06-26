"""平仄引擎领域正确性测试。

验证入声字判定和经典诗词平仄分析的正确性。
这是守护领域正确性的核心测试。
"""

import pytest
from openprom.engines.pingze import get_engine, get_sequence, PingZeValue


class TestRushengDetection:
    """入声字应判为仄声（中古汉语规则）"""

    @pytest.fixture
    def engine(self):
        return get_engine()

    def test_rusheng_chars_are_ze(self, engine):
        """常见入声字在今音中分散为平/上/去，但律诗中一律算仄声"""
        # 这些字今音为阳平(2声)，但中古是入声→应判为仄
        modern_ping_but_rusheng = [
            "白",
            "石",
            "国",
            "独",
            "读",
            "竹",
            "福",
            "服",
            "伏",
            "俗",
            "族",
            "足",
            "局",
            "席",
            "籍",
            "敌",
            "笛",
            "迪",
            "辑",
            "集",
            "及",
            "极",
            "急",
            "疾",
            "吉",
            "即",
            "节",
            "杰",
            "洁",
            "结",
            "劫",
            "竭",
            "截",
            "捷",
            "睫",
        ]
        for char in modern_ping_but_rusheng:
            result = engine.analyze(char)
            assert result.pingze == PingZeValue.ZE, (
                f"「{char}」中古入声字，应判为仄声，实际={result.pingze}，method={result.method}"
            )

    def test_rusheng_method_is_rusheng(self, engine):
        """韵书查不到的入声字应通过 rusheng 方法判定"""
        # 找一个在 rusheng 表中但不在韵书中的字
        for char in ["迪", "辑", "籍", "睫"]:
            result = engine.analyze(char)
            if result.method == "rusheng":
                assert result.confidence == 0.90
                assert result.pingze == PingZeValue.ZE
                return
        # 如果所有字都在韵书中，跳过此测试
        pytest.skip("所有测试入声字均在韵书中覆盖")

    def test_rusheng_chars_modern_ze_still_ze(self, engine):
        """今音为仄的入声字仍应判为仄"""
        modern_ze_rusheng = [
            "月",
            "雪",
            "色",
            "业",
            "叶",
            "绝",
            "铁",
            "帖",
            "塔",
            "踏",
            "纳",
            "杂",
            "合",
            "答",
            "搭",
            "鸽",
            "割",
            "葛",
            "渴",
            "喝",
            "脱",
            "夺",
            "括",
            "阔",
        ]
        for char in modern_ze_rusheng:
            result = engine.analyze(char)
            assert result.pingze == PingZeValue.ZE, f"「{char}」应为仄声"

    def test_non_rusheng_chars_unaffected(self, engine):
        """非入声字不应被误判"""
        # 常用平声字（非入声）
        ping_chars = ["春", "风", "花", "天", "山", "水", "人", "心"]
        for char in ping_chars:
            result = engine.analyze(char)
            # 这些字要么在韵书里查到，要么通过 pypinyin 判定
            # 关键是不能被误判为入声
            assert result.method != "rusheng", f"「{char}」不是入声字，不应通过 rusheng 判定"


class TestClassicalPoemPingze:
    """经典诗词的平仄序列应符合中古汉语规则"""

    def test_rusheng_in_poem_context(self):
        """含入声字的诗句平仄序列应正确"""
        # "风急天高猿啸哀" — 急(入声→仄) 应为 -1
        seq = get_sequence("风急天高猿啸哀")
        assert len(seq) == 7
        assert seq[1] == -1, f"「急」应为仄声(入声)，实际={seq[1]}"

    def test_white_in_poem(self):
        """「白」在诗中应为仄声"""
        # "白日依山尽" — 白(入声→仄)
        seq = get_sequence("白日依山尽")
        assert seq[0] == -1, f"「白」应为仄声(入声)，实际={seq[0]}"

    def test_moon_in_poem(self):
        """「月」在诗中应为仄声"""
        # "明月松间照" — 月(入声→仄)
        seq = get_sequence("明月松间照")
        assert seq[1] == -1, f"「月」应为仄声(入声)，实际={seq[1]}"

    def test_snow_in_poem(self):
        """「雪」在诗中应为仄声"""
        # "窗含西岭千秋雪" — 雪(入声→仄)
        seq = get_sequence("窗含西岭千秋雪")
        assert seq[6] == -1, f"「雪」应为仄声(入声)，实际={seq[6]}"

    def test_country_in_poem(self):
        """「国」在诗中应为仄声"""
        # "国破山河在" — 国(入声→仄)
        seq = get_sequence("国破山河在")
        assert seq[0] == -1, f"「国」应为仄声(入声)，实际={seq[0]}"


class TestRushengTableIntegrity:
    """入声字表的完整性检查"""

    def test_rusheng_table_loaded(self):
        """入声字表应成功加载"""
        engine = get_engine()
        assert len(engine._rusheng_chars) > 100, (
            f"入声字表应有 100+ 字，实际 {len(engine._rusheng_chars)} 字"
        )

    def test_rusheng_table_has_common_chars(self):
        """入声字表应包含常用入声字"""
        engine = get_engine()
        must_have = {
            "白",
            "石",
            "月",
            "雪",
            "国",
            "色",
            "竹",
            "独",
            "读",
            "福",
            "服",
            "局",
            "足",
            "族",
            "急",
            "及",
            "节",
            "绝",
        }
        missing = must_have - engine._rusheng_chars
        assert not missing, f"入声字表缺少: {missing}"
