"""数据加载模块

提供韵书、诗律、词谱等数据的加载和解析功能。
"""

import json
import os
import threading
from typing import Dict, List, Optional


# 数据目录路径
_DATA_DIR = os.path.dirname(os.path.abspath(__file__))


class RhymeBook:
    """韵书数据管理器（线程安全单例）

    支持多韵书查询，默认使用《平水韵》。
    """

    _instance: Optional['RhymeBook'] = None
    _data: Optional[Dict] = None
    _lock: threading.Lock = threading.Lock()
    _loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get(cls) -> 'RhymeBook':
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            cls()
        with cls._lock:
            if not cls._loaded:
                cls._load()
        return cls._instance

    @classmethod
    def _load(cls) -> None:
        """加载韵书数据（线程安全）"""
        path = os.path.join(_DATA_DIR, "rhymebooks.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                cls._data = json.load(f)
            cls._loaded = True
        except FileNotFoundError:
            raise FileNotFoundError(f"韵书数据文件不存在: {path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"韵书数据格式错误: {e}")

    def get_tone(self, char: str, book: str = "平水韵") -> Optional[int]:
        """查询汉字在指定韵书中的平仄

        Args:
            char: 待查询的汉字
            book: 韵书名称，默认"平水韵"

        Returns:
            1=平声, -1=仄声, None=未找到
        """
        if self._data is None or book not in self._data:
            return None

        book_data = self._data[book]
        if not isinstance(book_data, list) or len(book_data) < 2:
            return None

        ping_list = book_data[0]  # 平声韵部
        ze_list = book_data[1]    # 仄声韵部

        # 在平声韵部中查找
        for category in ping_list:
            if char in category:
                return 1

        # 在仄声韵部中查找
        for category in ze_list:
            if char in category:
                return -1

        return None

    def list_books(self) -> List[str]:
        """列出所有可用的韵书"""
        if self._data is None:
            return []
        return list(self._data.keys())

    def get_rhyme_category(self, char: str, book: str = "平水韵") -> Optional[str]:
        """查询汉字在指定韵书中的韵部名称

        Args:
            char: 待查询的汉字
            book: 韵书名称，默认"平水韵"

        Returns:
            韵部名称（每组首字），None=未找到
        """
        if self._data is None or book not in self._data:
            return None

        book_data = self._data[book]
        if not isinstance(book_data, list) or len(book_data) < 2:
            return None

        for category_group in book_data[0] + book_data[1]:
            if char in category_group:
                return category_group[0]

        return None

    def get_book_info(self, book: str) -> Optional[Dict]:
        """获取韵书信息"""
        if self._data is None or book not in self._data:
            return None

        book_data = self._data[book]
        if isinstance(book_data, list) and len(book_data) >= 2:
            return {
                "name": book,
                "ping_categories": len(book_data[0]),
                "ze_categories": len(book_data[1]),
                "total_chars": sum(len(c) for c in book_data[0]) + sum(len(c) for c in book_data[1])
            }
        return None


class MeterPattern:
    """诗律词谱模式管理器（线程安全单例）

    管理诗体（五律、七律等）和词牌（蝶恋花、浣溪沙等）的格律模式。
    """

    _instance: Optional['MeterPattern'] = None
    _shi_data: Optional[Dict[str, str]] = None
    _ci_data: Optional[Dict[str, str]] = None
    _lock: threading.Lock = threading.Lock()
    _loaded: bool = False

    # 模式编码映射
    _PATTERN_MAP = {
        '0': 0,   # 可平可仄
        '1': 1,   # 平声
        '2': -1,  # 仄声
        '3': 3,   # 必须是平
        '4': 4,   # 必须是仄
    }

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get(cls) -> 'MeterPattern':
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            cls()
        with cls._lock:
            if not cls._loaded:
                cls._load()
        return cls._instance

    @classmethod
    def _load(cls) -> None:
        """加载诗律词谱数据（线程安全）"""
        shi_path = os.path.join(_DATA_DIR, "meters.json")
        ci_path = os.path.join(_DATA_DIR, "ci-meters.json")

        try:
            with open(shi_path, "r", encoding="utf-8") as f:
                cls._shi_data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"诗律数据文件不存在: {shi_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"诗律数据格式错误: {e}")

        try:
            with open(ci_path, "r", encoding="utf-8") as f:
                cls._ci_data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"词谱数据文件不存在: {ci_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"词谱数据格式错误: {e}")
        
        cls._loaded = True

    def _parse_pattern(self, pattern_str: str) -> List[List[int]]:
        """解析格律模式字符串

        Args:
            pattern_str: 逗号分隔的模式字符串，如 "11122,22213"

        Returns:
            二维整数列表
        """
        lines = pattern_str.split(",")
        result = []

        for line in lines:
            row = []
            for char in line.strip():
                if char in self._PATTERN_MAP:
                    row.append(self._PATTERN_MAP[char])
                else:
                    # 忽略未知字符
                    continue
            if row:  # 只添加非空行
                result.append(row)

        return result

    def get_shi_pattern(self, name: str) -> Optional[List[List[int]]]:
        """获取诗体格律模式

        Args:
            name: 诗体名称，如"五律平起首句不入韵"

        Returns:
            格律模式二维列表
        """
        if self._shi_data is None or name not in self._shi_data:
            return None

        pattern_str = self._shi_data[name]
        return self._parse_pattern(pattern_str)

    def get_ci_pattern(self, name: str) -> Optional[List[List[int]]]:
        """获取词牌格律模式

        Args:
            name: 词牌名称，如"蝶恋花"

        Returns:
            格律模式二维列表
        """
        if self._ci_data is None or name not in self._ci_data:
            return None

        pattern_str = self._ci_data[name]
        return self._parse_pattern(pattern_str)

    def list_shi_patterns(self) -> List[str]:
        """列出所有诗体名称"""
        if self._shi_data is None:
            return []
        return list(self._shi_data.keys())

    def list_ci_patterns(self) -> List[str]:
        """列出所有词牌名称"""
        if self._ci_data is None:
            return []
        return list(self._ci_data.keys())

    def search_shi(self, keyword: str) -> List[str]:
        """搜索诗体"""
        if self._shi_data is None:
            return []
        return [name for name in self._shi_data.keys() if keyword in name]

    def search_ci(self, keyword: str) -> List[str]:
        """搜索词牌"""
        if self._ci_data is None:
            return []
        return [name for name in self._ci_data.keys() if keyword in name]

    def get_pattern_info(self, name: str, pattern_type: str = "shi") -> Optional[Dict]:
        """获取格律模式信息

        Args:
            name: 模式名称
            pattern_type: 'shi' 或 'ci'

        Returns:
            模式信息字典
        """
        if pattern_type == "shi":
            pattern = self.get_shi_pattern(name)
            source = "诗体"
        elif pattern_type == "ci":
            pattern = self.get_ci_pattern(name)
            source = "词牌"
        else:
            return None

        if pattern is None:
            return None

        return {
            "name": name,
            "type": source,
            "lines": len(pattern),
            "chars_per_line": [len(line) for line in pattern],
            "total_chars": sum(len(line) for line in pattern),
        }
