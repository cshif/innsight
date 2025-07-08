"""
Parser module for extracting days and filters from Chinese text queries.

This module provides functionality to parse Chinese text queries for:
1. Duration extraction (days/nights) with support for both Arabic and Chinese numerals
2. Filter extraction for accommodation features (parking, wheelchair access, kids-friendly, pet-friendly)
3. POI (Point of Interest) extraction for main travel activities and attractions
4. Location extraction from query text and POI keywords
"""

import re
import os
from functools import lru_cache
from typing import List, Optional, Dict, Set


class DaysOutOfRangeError(Exception):
    """Exception raised when extracted days exceed the valid range (>14 days)."""
    pass


class ParseConflictError(Exception):
    """Exception raised when there are conflicting day specifications in the same text."""
    pass


class ChineseNumberParser:
    """Helper class for parsing Chinese numbers."""
    
    CHINESE_NUMBERS = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15, '十六': 16,
        '十七': 17, '十八': 18, '十九': 19, '二十': 20, '兩': 2, '半': 0.5
    }
    
    @classmethod
    def parse(cls, text: str) -> int:
        """Parse Chinese number text to integer."""
        if text.isdigit():
            return int(text)
        return cls.CHINESE_NUMBERS.get(text, 0)


class DaysExtractor:
    """Extractor for duration information from Chinese text."""
    
    # Note: Day and night patterns are now handled directly in _extract_all_days method
    # to properly distinguish between day and night patterns for logical validation
    
    # Patterns that should return None (half day)
    HALF_DAY_PATTERNS = [r'半天', r'半日']
    
    # Maximum allowed days
    MAX_DAYS = 14
    
    def __init__(self):
        self.number_parser = ChineseNumberParser()
    
    def extract(self, text: str | None) -> Optional[int]:
        """
        Extract number of days from Chinese text.
        
        Args:
            text: Input text string
            
        Returns:
            int: Number of days (1-14) or None if no valid days found
            
        Raises:
            DaysOutOfRangeError: If days > 14
            ParseConflictError: If conflicting day specifications found
        """
        if not text or not isinstance(text, str):
            return None
        
        # Check for half day patterns first
        if self._is_half_day(text):
            return None
        
        # Extract all day matches
        found_days = self._extract_all_days(text)
        
        if not found_days:
            return None
        
        # Resolve conflicts and validate
        resolved_days = self._resolve_conflicts(found_days)
        self._validate_range(resolved_days)
        
        return resolved_days
    
    def _is_half_day(self, text: str) -> bool:
        """Check if text contains half day patterns."""
        return any(re.search(pattern, text) for pattern in self.HALF_DAY_PATTERNS)
    
    def _extract_all_days(self, text: str) -> List[int]:
        """Extract all day numbers from text."""
        found_days = []
        day_counts = []  # Track actual day counts vs night counts
        night_counts = []  # Track night counts
        
        # Pattern for days (天/日)
        day_pattern = r'(\d+|一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四|十五|十六|十七|十八|十九|二十|兩)[，\s]*[天日]'
        matches = re.findall(day_pattern, text)
        for match in matches:
            day_num = self.number_parser.parse(match)
            if day_num == 0.5:  # Half day
                return []  # Return empty to indicate None result
            if day_num > 0:
                found_days.append(day_num)
                day_counts.append(day_num)
        
        # Pattern for nights (晚/夜)
        night_pattern = r'(\d+|一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四|十五|十六|十七|十八|十九|二十|兩)[，\s]*[晚夜]'
        matches = re.findall(night_pattern, text)
        for match in matches:
            night_num = self.number_parser.parse(match)
            if night_num == 0.5:  # Half night
                return []  # Return empty to indicate None result
            if night_num > 0:
                found_days.append(night_num)
                night_counts.append(night_num)
        
        # Check for specific illogical combinations like "一天兩夜"
        if day_counts and night_counts:
            # Special case: exactly one day and exactly one night value
            if len(day_counts) == 1 and len(night_counts) == 1:
                day_val = day_counts[0]
                night_val = night_counts[0]
                # If day < night and it's a small difference, treat as illogical
                if day_val < night_val and (night_val - day_val) <= 1:
                    return []  # Return empty to indicate None result (illogical)
            # For more complex cases with multiple values, let _resolve_conflicts handle it
        
        return found_days
    
    def _resolve_conflicts(self, found_days: List[int]) -> int:
        """Resolve conflicts in day specifications."""
        unique_days = set(found_days)
        
        if len(unique_days) == 1:
            return found_days[0]
        
        # Allow common patterns like "兩天一夜" (2 days 1 night)
        if len(unique_days) == 2:
            sorted_days = sorted(unique_days)
            if sorted_days[1] - sorted_days[0] == 1:
                return max(found_days)  # Use the larger number (days, not nights)
        
        raise ParseConflictError(f"Conflicting day specifications found: {list(unique_days)}")
    
    def _validate_range(self, days: int) -> None:
        """Validate that days are within acceptable range."""
        if days > self.MAX_DAYS:
            raise DaysOutOfRangeError(f"Days {days} exceeds maximum of {self.MAX_DAYS}")


class FilterExtractor:
    """Extractor for filter categories from segmented tokens."""
    
    FILTER_MAPPINGS = {
        'parking': ['停車', '好停車', '停車場', '車位', '停車位'],
        'wheelchair': ['無障礙', '輪椅', '行動不便', '殘障', '無障礙設施'],
        'kids': ['親子', '兒童', '小孩', '孩子', '小朋友', '親子友善'],
        'pet': ['寵物', '狗', '貓', '毛孩', '寵物友善', '可攜帶寵物']
    }
    
    def extract(self, tokens: List[str] | None) -> List[str]:
        """
        Extract filter categories from segmented word tokens.
        
        Args:
            tokens: List of segmented words
            
        Returns:
            List[str]: List of filter categories (no duplicates, order not guaranteed)
        """
        if not tokens or not isinstance(tokens, list):
            return []
        
        # Combine tokens to catch split keywords
        text_combined = self._combine_tokens(tokens)
        
        # Find matching filters
        found_filters = self._find_matching_filters(tokens, text_combined)
        
        return list(found_filters)
    
    def _combine_tokens(self, tokens: List[str]) -> str:
        """Safely combine tokens into a single string."""
        try:
            return ''.join(str(token) for token in tokens if token is not None)
        except (TypeError, AttributeError):
            return ''
    
    def _find_matching_filters(self, tokens: List[str], combined_text: str) -> Set[str]:
        """Find all matching filter categories."""
        found_filters = set()
        
        for filter_category, keywords in self.FILTER_MAPPINGS.items():
            if self._has_matching_keyword(keywords, tokens, combined_text):
                found_filters.add(filter_category)
        
        return found_filters
    
    def _has_matching_keyword(self, keywords: List[str], tokens: List[str], combined_text: str) -> bool:
        """Check if any keyword matches in tokens or combined text."""
        for keyword in keywords:
            # Check in combined text or individual tokens
            if (keyword in combined_text or 
                any(keyword in str(token) for token in tokens 
                    if token is not None and isinstance(token, (str, int)))):
                return True
        return False


class PoiExtractor:
    """Extractor for main travel POI (Point of Interest) activities and attractions."""
    
    POI_MAPPINGS = {
        'sightseeing': {
            'keywords': ['美ら海水族館', '首里城', '萬座毛', '國際通', '殘波岬', '古宇利島', 
                        '部瀨名海中公園', '琉球玻璃村', 'DFS', '美國村', '新都心'],
            'patterns': [r'去.*看.*', r'參觀.*', r'逛.*', r'看.*景']
        },
        'culture': {
            'keywords': ['琉球村', '傳統工藝', '琉球文化', '民俗村', '文化村', '傳統', '工藝', 
                        '歷史', '博物館', '文化體驗', '手作', '陶藝'],
            'patterns': [r'體驗.*文化', r'學.*傳統', r'.*工藝.*', r'文化.*']
        },
        'historical': {
            'keywords': ['今歸仁', '遺跡', '古蹟', '城跡', '史跡', '古城', '歷史遺跡',
                        '中城城跡', '勝連城跡', '座喜味城跡'],
            'patterns': [r'.*遺跡.*', r'.*古蹟.*', r'.*城跡.*', r'歷史.*']
        },
        'nature': {
            'keywords': ['海灘', '潛水', '海景', '海', '海水', '海邊', '沙灘', '浮潛', 
                        '海中', '海底', '珊瑚', '熱帶魚', '瀨底島', '水納島'],
            'patterns': [r'.*海.*玩', r'.*潛水.*', r'看.*海', r'玩.*水', r'.*海景.*']
        },
        'food': {
            'keywords': ['沖繩料理', '當地美食', '海葡萄', '苦瓜', '紅芋', '沖繩麵', 
                        '三線魚', '豬腳', '泡盛', 'A&W', '藍封', 'Blue Seal'],
            'patterns': [r'吃.*', r'嘗.*', r'品.*', r'美食.*', r'料理.*']
        },
        'shopping': {
            'keywords': ['購物', '逛街', '買東西', '購物中心', '商場', '免稅店', 'DFS', 
                        '新都心', 'AEON', '永旺', '購買', '血拚'],
            'patterns': [r'.*購物.*', r'.*逛街.*', r'買.*', r'購買.*']
        },
        'entertainment': {
            'keywords': ['海豚', '表演', '秀', '娛樂', '遊樂園', '主題樂園', '水族館表演',
                        '海豚秀', '鯨鯊', '動物表演', '音樂', '舞蹈'],
            'patterns': [r'看.*表演', r'.*秀.*', r'.*娛樂.*', r'玩.*']
        },
        'transportation': {
            'keywords': ['租車', '包車', '巴士', '電車', '單軌', '計程車', '交通',
                        '機場', '那霸機場', '港口', '輪船'],
            'patterns': [r'.*租車.*', r'.*包車.*', r'交通.*', r'.*機場.*']
        }
    }
    
    def extract(self, tokens: List[str] | None) -> List[str]:
        """
        Extract POI categories from segmented word tokens.
        
        Args:
            tokens: List of segmented words
            
        Returns:
            List[str]: List of POI categories (no duplicates, order not guaranteed)
        """
        if not tokens or not isinstance(tokens, list):
            return []
        
        # Combine tokens to catch split keywords
        text_combined = self._combine_tokens(tokens)
        
        # Find matching POI categories
        found_categories = self._find_matching_categories(tokens, text_combined)
        
        return list(found_categories)
    
    def _combine_tokens(self, tokens: List[str]) -> str:
        """Safely combine tokens into a single string."""
        try:
            return ''.join(str(token) for token in tokens if token is not None)
        except (TypeError, AttributeError):
            return ''
    
    def _find_matching_categories(self, tokens: List[str], combined_text: str) -> Set[str]:
        """Find all matching POI categories."""
        found_categories = set()
        
        for category, config in self.POI_MAPPINGS.items():
            if self._has_matching_category(config, tokens, combined_text):
                found_categories.add(category)
        
        return found_categories
    
    def _has_matching_category(self, config: Dict, tokens: List[str], combined_text: str) -> bool:
        """Check if any keyword or pattern matches for a category."""
        # Check keywords
        for keyword in config['keywords']:
            if (keyword in combined_text or 
                any(keyword in str(token) for token in tokens 
                    if token is not None and isinstance(token, (str, int)))):
                return True
        
        # Check patterns
        for pattern in config['patterns']:
            if re.search(pattern, combined_text):
                return True
                
        return False


class JiebaTokenizer:
    """Tokenizer using jieba with custom dictionary support."""
    
    def __init__(self):
        self._jieba_available = self._try_import_jieba()
        self._dict_loaded = False
    
    def _try_import_jieba(self) -> bool:
        """Try to import jieba and return availability."""
        try:
            import jieba
            self._jieba = jieba
            return True
        except ImportError:
            return False
    
    def _load_custom_dict(self) -> None:
        """Load custom dictionary if available."""
        if self._dict_loaded or not self._jieba_available:
            return
        
        try:
            dict_path = os.path.join(os.path.dirname(__file__), "..", "resources", "user_dict.txt")
            if os.path.exists(dict_path):
                self._jieba.load_userdict(dict_path)
            self._dict_loaded = True
        except Exception:
            pass  # Fail silently if dictionary loading fails
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text using jieba or fallback method."""
        if not self._jieba_available:
            return [text]  # Fallback: use whole text as single token
        
        self._load_custom_dict()
        return self._jieba.lcut(text)


class QueryParser:
    """Main parser class that combines days, filters, and POI extraction."""
    
    def __init__(self):
        self.days_extractor = DaysExtractor()
        self.filter_extractor = FilterExtractor()
        self.poi_extractor = PoiExtractor()
        self.tokenizer = JiebaTokenizer()
    
    def parse(self, text: str) -> Dict[str, any]:
        """
        Parse query text to extract days, filters, and POI.
        
        Args:
            text: Input query text
            
        Returns:
            dict: Dictionary containing 'days', 'filters', and 'poi' keys
        """
        try:
            # Tokenize text
            tokens = self.tokenizer.tokenize(text)
            
            # Extract days, filters, and POI
            days = self.days_extractor.extract(text)
            filters = self.filter_extractor.extract(tokens)
            poi = self.poi_extractor.extract(tokens)
            
            return {
                'days': days,
                'filters': filters,
                'poi': poi
            }
            
        except Exception:
            # Fallback: minimal parsing
            days = self.days_extractor.extract(text)
            filters = self.filter_extractor.extract([text])
            poi = self.poi_extractor.extract([text])
            
            return {
                'days': days,
                'filters': filters,
                'poi': poi
            }


# Cached parser instance using lru_cache
@lru_cache(maxsize=1)
def _get_default_parser() -> QueryParser:
    """Get the default parser instance, creating it if necessary."""
    return QueryParser()


# Cache clearing function for tests
def clear_parser_cache() -> None:
    """Clear the parser cache. Useful for testing."""
    _get_default_parser.cache_clear()


# Public API functions with optional dependency injection
def extract_days(text: str | None, parser: Optional[QueryParser] = None) -> Optional[int]:
    """Extract number of days from Chinese text."""
    if parser is None:
        parser = _get_default_parser()
    return parser.days_extractor.extract(text)


def extract_filters(tokens: List[str] | None, parser: Optional[QueryParser] = None) -> List[str]:
    """Extract filter categories from segmented word tokens."""
    if parser is None:
        parser = _get_default_parser()
    return parser.filter_extractor.extract(tokens)


def extract_poi(tokens: List[str] | None, parser: Optional[QueryParser] = None) -> List[str]:
    """Extract POI categories from segmented word tokens."""
    if parser is None:
        parser = _get_default_parser()
    return parser.poi_extractor.extract(tokens)


def parse_query(text: str, parser: Optional[QueryParser] = None) -> Dict[str, any]:
    """Parse query text to extract days, filters, and POI."""
    if parser is None:
        parser = _get_default_parser()
    return parser.parse(text)


def extract_location_from_query(parsed_query: dict, original_query: str) -> str | None:
    """從解析結果和原始查詢中提取具體地點或景點信息"""
    
    # 優先檢查 POI 中是否有特定地點
    if parsed_query and parsed_query.get('poi'):
        # 沖繩相關地點關鍵詞
        okinawa_keywords = [
            '美ら海水族館', '首里城', '萬座毛', '國際通', '殘波岬', '古宇利島',
            '部瀨名海中公園', '琉球玻璃村', 'DFS', '美國村', '新都心',
            '琉球村', '今歸仁', '中城城跡', '勝連城跡', '座喜味城跡',
            '瀨底島', '水納島', '那霸機場'
        ]
        
        # 優先返回具體的景點名稱
        for keyword in okinawa_keywords:
            if keyword in original_query:
                return keyword
    
    # 直接檢查原始查詢中的地點
    location_keywords = {
        '沖繩': '沖繩',
        '台北': '台北',
        '東京': '東京',
        '大阪': '大阪',
        '京都': '京都',
        '那霸': '沖繩',
        'Okinawa': '沖繩'
    }
    
    for keyword, location in location_keywords.items():
        if keyword in original_query:
            return location
    
    return None