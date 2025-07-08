"""
Comprehensive test suite for parser module covering all requirements.

This test suite validates:
1. API output format consistency
2. Days extraction with Arabic and Chinese numerals
3. Filter extraction for accommodation features
4. Boundary conditions and error scenarios
5. Performance requirements
6. Integration testing
"""

from pytest import raises, fail, main
import time
import random
from typing import List

from scripts.parser import (
    extract_days, extract_filters, extract_poi, parse_query,
    DaysOutOfRangeError, ParseConflictError,
    DaysExtractor, FilterExtractor, PoiExtractor, ChineseNumberParser
)


class TestChineseNumberParser:
    """Test the Chinese number parser helper class."""
    
    def test_arabic_numbers(self):
        """Test parsing of Arabic numerals."""
        assert ChineseNumberParser.parse("1") == 1
        assert ChineseNumberParser.parse("10") == 10
        assert ChineseNumberParser.parse("99") == 99
    
    def test_chinese_numbers(self):
        """Test parsing of Chinese numerals."""
        assert ChineseNumberParser.parse("一") == 1
        assert ChineseNumberParser.parse("二") == 2
        assert ChineseNumberParser.parse("十") == 10
        assert ChineseNumberParser.parse("兩") == 2
        assert ChineseNumberParser.parse("半") == 0.5
    
    def test_invalid_numbers(self):
        """Test parsing of invalid number strings."""
        assert ChineseNumberParser.parse("abc") == 0
        assert ChineseNumberParser.parse("") == 0
        assert ChineseNumberParser.parse("unknown") == 0


class TestDaysExtractor:
    """Test the days extraction functionality."""
    
    def setup(self):
        """Set up test fixtures."""
        self.extractor = DaysExtractor()
    
    def test_arabic_numerals_with_units(self):
        """Test Arabic numerals with different day units."""
        extractor = DaysExtractor()
        assert extractor.extract("預計待2天") == 2
        assert extractor.extract("住3日") == 3
        assert extractor.extract("待4晚") == 4
        assert extractor.extract("住5夜") == 5
    
    def test_chinese_numerals_with_units(self):
        """Test Chinese numerals with different day units."""
        extractor = DaysExtractor()
        assert extractor.extract("想住兩天一夜") == 2
        assert extractor.extract("打算住三晚") == 3
        assert extractor.extract("住一天") == 1
        assert extractor.extract("四日遊") == 4
    
    def test_half_day_patterns(self):
        """Test that half day patterns return None."""
        extractor = DaysExtractor()
        assert extractor.extract("只去半天") is None
        assert extractor.extract("半日遊") is None
        assert extractor.extract("想住一天兩夜") is None

    def test_comprehensive_number_coverage(self):
        """Test comprehensive coverage of numbers and units."""
        extractor = DaysExtractor()
        
        # Test Arabic numbers 1-14 with all units
        for i in range(1, 15):
            assert extractor.extract(f"住{i}天") == i
            assert extractor.extract(f"待{i}日") == i
            assert extractor.extract(f"住{i}晚") == i
        
        # Test Chinese numbers with units
        chinese_nums = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, 
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '十一': 11, '十二': 12, '十三': 13, '十四': 14, '兩': 2
        }
        
        for chinese, num in chinese_nums.items():
            assert extractor.extract(f"住{chinese}天") == num
            assert extractor.extract(f"待{chinese}日") == num
            assert extractor.extract(f"住{chinese}晚") == num
    
    def test_days_out_of_range(self):
        """Test that days > 14 raise DaysOutOfRangeError."""
        extractor = DaysExtractor()
        
        with raises(DaysOutOfRangeError):
            extractor.extract("住二十天")
        with raises(DaysOutOfRangeError):
            extractor.extract("住15天")
        with raises(DaysOutOfRangeError):
            extractor.extract("住100天")
    
    def test_conflicting_days(self):
        """Test that conflicting day specifications raise ParseConflictError."""
        extractor = DaysExtractor()
        
        with raises(ParseConflictError):
            extractor.extract("兩天一夜三晚")
        with raises(ParseConflictError):
            extractor.extract("住2天待5晚")
        with raises(ParseConflictError):
            extractor.extract("住1天待3晚")
    
    def test_acceptable_patterns(self):
        """Test that acceptable patterns like '兩天一夜' work correctly."""
        extractor = DaysExtractor()
        
        # These should work (N天(N-1)夜 patterns)
        assert extractor.extract("兩天一夜") == 2
        assert extractor.extract("三天二夜") == 3
        assert extractor.extract("四天三晚") == 4
    
    def test_edge_cases(self):
        """Test edge cases and invalid inputs."""
        extractor = DaysExtractor()
        
        assert extractor.extract(None) is None
        assert extractor.extract("") is None
        assert extractor.extract("沒有天數") is None
        assert extractor.extract("隨機文字") is None
        assert extractor.extract("123abc") is None


class TestFilterExtractor:
    """Test the filter extraction functionality."""
    
    def test_parking_keywords(self):
        """Test parking-related keyword detection."""
        extractor = FilterExtractor()
        
        parking_keywords = ['停車', '好停車', '停車場', '車位', '停車位']
        for keyword in parking_keywords:
            result = extractor.extract([keyword])
            assert 'parking' in result
    
    def test_wheelchair_keywords(self):
        """Test wheelchair accessibility keyword detection."""
        extractor = FilterExtractor()
        
        wheelchair_keywords = ['無障礙', '輪椅', '行動不便', '殘障', '無障礙設施']
        for keyword in wheelchair_keywords:
            result = extractor.extract([keyword])
            assert 'wheelchair' in result
    
    def test_kids_keywords(self):
        """Test kids-friendly keyword detection."""
        extractor = FilterExtractor()
        
        kids_keywords = ['親子', '兒童', '小孩', '孩子', '小朋友', '親子友善']
        for keyword in kids_keywords:
            result = extractor.extract([keyword])
            assert 'kids' in result
    
    def test_pet_keywords(self):
        """Test pet-friendly keyword detection."""
        extractor = FilterExtractor()
        
        pet_keywords = ['寵物', '狗', '貓', '毛孩', '寵物友善', '可攜帶寵物']
        for keyword in pet_keywords:
            result = extractor.extract([keyword])
            assert 'pet' in result
    
    def test_multiple_filters(self):
        """Test extraction of multiple filter categories."""
        extractor = FilterExtractor()
        
        result = extractor.extract(['要', '好停車', '無障礙'])
        assert 'parking' in result
        assert 'wheelchair' in result
        assert len(result) == 2
        
        result = extractor.extract(['親子', '友善', '寵物', '可入住'])
        assert 'kids' in result
        assert 'pet' in result
        assert len(result) == 2
    
    def test_no_duplicates(self):
        """Test that results contain no duplicates."""
        extractor = FilterExtractor()
        
        result = extractor.extract(['停車', '好停車', '停車場'])
        assert len(result) == 1
        assert 'parking' in result
    
    def test_split_keywords(self):
        """Test handling of keywords split across tokens."""
        extractor = FilterExtractor()
        
        # Test when jieba splits "無障礙" into ['無', '障礙']
        result = extractor.extract(['要', '無', '障礙', '設施'])
        assert 'wheelchair' in result
    
    def test_no_matches(self):
        """Test when no filter keywords are found."""
        extractor = FilterExtractor()
        
        result = extractor.extract(['想', '住飯店'])
        assert result == []
    
    def test_edge_cases(self):
        """Test edge cases and invalid inputs."""
        extractor = FilterExtractor()
        
        assert extractor.extract(None) == []
        assert extractor.extract([]) == []
        assert extractor.extract([None]) == []
        assert extractor.extract([123]) == []
        assert extractor.extract(['random', 'strings']) == []


class TestPoiExtractor:
    """Test the POI extraction functionality."""
    
    def test_sightseeing_keywords(self):
        """Test sightseeing-related keyword detection."""
        extractor = PoiExtractor()
        
        sightseeing_keywords = ['美ら海水族館', '首里城', '萬座毛', '國際通', 'DFS', '新都心']
        for keyword in sightseeing_keywords:
            result = extractor.extract([keyword])
            assert 'sightseeing' in result
    
    def test_culture_keywords(self):
        """Test culture-related keyword detection."""
        extractor = PoiExtractor()
        
        culture_keywords = ['琉球村', '傳統工藝', '琉球文化', '文化體驗', '手作', '陶藝']
        for keyword in culture_keywords:
            result = extractor.extract([keyword])
            assert 'culture' in result
    
    def test_historical_keywords(self):
        """Test historical-related keyword detection."""
        extractor = PoiExtractor()
        
        historical_keywords = ['今歸仁', '遺跡', '古蹟', '城跡', '歷史遺跡', '中城城跡']
        for keyword in historical_keywords:
            result = extractor.extract([keyword])
            assert 'historical' in result
    
    def test_nature_keywords(self):
        """Test nature-related keyword detection."""
        extractor = PoiExtractor()
        
        nature_keywords = ['海灘', '潛水', '海景', '浮潛', '珊瑚', '熱帶魚']
        for keyword in nature_keywords:
            result = extractor.extract([keyword])
            assert 'nature' in result
    
    def test_food_keywords(self):
        """Test food-related keyword detection."""
        extractor = PoiExtractor()
        
        food_keywords = ['沖繩料理', '當地美食', '海葡萄', '沖繩麵', '泡盛']
        for keyword in food_keywords:
            result = extractor.extract([keyword])
            assert 'food' in result
    
    def test_shopping_keywords(self):
        """Test shopping-related keyword detection."""
        extractor = PoiExtractor()
        
        shopping_keywords = ['購物', '逛街', '買東西', '購物中心', 'AEON', '血拚']
        for keyword in shopping_keywords:
            result = extractor.extract([keyword])
            assert 'shopping' in result
    
    def test_entertainment_keywords(self):
        """Test entertainment-related keyword detection."""
        extractor = PoiExtractor()
        
        entertainment_keywords = ['海豚', '表演', '秀', '娛樂', '海豚秀', '動物表演']
        for keyword in entertainment_keywords:
            result = extractor.extract([keyword])
            assert 'entertainment' in result
    
    def test_transportation_keywords(self):
        """Test transportation-related keyword detection."""
        extractor = PoiExtractor()
        
        transportation_keywords = ['租車', '包車', '巴士', '機場', '那霸機場', '交通']
        for keyword in transportation_keywords:
            result = extractor.extract([keyword])
            assert 'transportation' in result
    
    def test_pattern_matching(self):
        """Test regex pattern matching for POI categories."""
        extractor = PoiExtractor()
        
        # Test sightseeing patterns
        result = extractor.extract(['去', '看', '風景'])
        assert 'sightseeing' in result
        
        result = extractor.extract(['參觀', '博物館'])
        assert 'sightseeing' in result
        
        # Test food patterns
        result = extractor.extract(['吃', '當地', '特色'])
        assert 'food' in result
        
        # Test nature patterns
        result = extractor.extract(['玩', '水', '活動'])
        assert 'nature' in result
    
    def test_multiple_categories(self):
        """Test extraction of multiple POI categories."""
        extractor = PoiExtractor()
        
        result = extractor.extract(['美ら海水族館', '吃', '沖繩料理'])
        assert 'sightseeing' in result
        assert 'nature' in result  # 美ら海水族館 matches both
        assert 'food' in result
        assert len(result) == 3
        
        result = extractor.extract(['購物', '看', '海豚', '表演'])
        assert 'shopping' in result
        assert 'entertainment' in result
        assert 'nature' in result
    
    def test_no_duplicates(self):
        """Test that results contain no duplicates."""
        extractor = PoiExtractor()
        
        result = extractor.extract(['美ら海水族館', '海景', '海灘'])
        # All should match 'nature' and 'sightseeing' categories
        assert 'nature' in result
        assert 'sightseeing' in result
        # Should not have duplicates
        assert len([x for x in result if x == 'nature']) == 1
        assert len([x for x in result if x == 'sightseeing']) == 1
    
    def test_no_matches(self):
        """Test when no POI keywords are found."""
        extractor = PoiExtractor()
        
        result = extractor.extract(['隨機', '文字', '測試'])
        assert result == []
    
    def test_edge_cases(self):
        """Test edge cases and invalid inputs."""
        extractor = PoiExtractor()
        
        assert extractor.extract(None) == []
        assert extractor.extract([]) == []
        assert extractor.extract([None]) == []
        assert extractor.extract([123]) == []
        assert extractor.extract(['random', 'strings']) == []


class TestApiOutputFormat:
    """Test API output format consistency."""
    
    def test_extract_days_return_type(self):
        """Test that extract_days returns int or None."""
        result = extract_days("預計待2天")
        assert isinstance(result, int) or result is None
        
        result = extract_days("沒有天數")
        assert result is None
        
        result = extract_days("")
        assert result is None
        
        result = extract_days(None)
        assert result is None
    
    def test_extract_filters_return_type(self):
        """Test that extract_filters returns List[str]."""
        result = extract_filters(['要', '好停車', '無障礙'])
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)
        
        result = extract_filters([])
        assert isinstance(result, list)
        assert result == []
        
        result = extract_filters(None)
        assert isinstance(result, list)
        assert result == []
    
    def test_extract_poi_return_type(self):
        """Test that extract_poi returns List[str]."""
        result = extract_poi(['美ら海水族館', '首里城'])
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)
        
        result = extract_poi([])
        assert isinstance(result, list)
        assert result == []
        
        result = extract_poi(None)
        assert isinstance(result, list)
        assert result == []


class TestIntegration:
    """Integration tests for the complete parsing functionality."""
    
    def test_parse_query_with_days_and_filters(self):
        """Test parse_query with both days and filters."""
        result = parse_query("想住兩天一夜，要好停車的親子友善飯店")
        assert result['days'] == 2
        assert 'parking' in result['filters']
        assert 'kids' in result['filters']
    
    def test_parse_query_days_only(self):
        """Test parse_query with only days."""
        result = parse_query("預計待3天")
        assert result['days'] == 3
        assert result['filters'] == []
    
    def test_parse_query_filters_only(self):
        """Test parse_query with only filters."""
        result = parse_query("要無障礙設施")
        assert result['days'] is None
        assert 'wheelchair' in result['filters']
    
    def test_parse_query_no_matches(self):
        """Test parse_query with no matches."""
        result = parse_query("隨機文字")
        assert result['days'] is None
        assert result['filters'] == []
    
    def test_parse_query_return_format(self):
        """Test that parse_query returns correct dictionary format."""
        result = parse_query("住2天")
        assert isinstance(result, dict)
        assert 'days' in result
        assert 'filters' in result
        assert 'poi' in result
        assert isinstance(result['filters'], list)
        assert isinstance(result['poi'], list)
    
    def test_parse_query_with_poi(self):
        """Test parse_query with POI extraction."""
        result = parse_query("想去美ら海水族館看海豚")
        assert result['days'] is None
        assert result['filters'] == []
        assert 'sightseeing' in result['poi']
        assert 'nature' in result['poi']
        assert 'entertainment' in result['poi']
    
    def test_parse_query_comprehensive(self):
        """Test parse_query with days, filters, and POI."""
        result = parse_query("住兩天去首里城參觀，要停車位和親子設施")
        assert result['days'] == 2
        assert 'parking' in result['filters']
        assert 'kids' in result['filters']
        assert 'sightseeing' in result['poi']


class TestErrorHandling:
    """Test error handling and boundary conditions."""
    
    def test_safe_error_handling_days(self):
        """Test that extract_days handles unexpected inputs safely."""
        test_cases = [
            None, "", "随机字符串", "123abc", "!@#$%^&*()",
            "🏨🚗🎯", "a" * 1000
        ]
        
        for test_input in test_cases:
            try:
                result = extract_days(test_input)
                assert result is None or isinstance(result, int)
            except (DaysOutOfRangeError, ParseConflictError):
                pass  # These are expected custom errors
            except Exception as e:
                fail(f"Unexpected exception for input '{test_input}': {e}")
    
    def test_safe_error_handling_filters(self):
        """Test that extract_filters handles unexpected inputs safely."""
        test_cases = [
            None, [], [""], [None], [123], ["random", "strings"]
        ]
        
        for test_input in test_cases:
            try:
                result = extract_filters(test_input)
                assert isinstance(result, list)
            except Exception as e:
                fail(f"Unexpected exception for input '{test_input}': {e}")


class TestPerformance:
    """Test performance requirements."""
    
    def generate_random_sentences(self, count: int, max_length: int = 100) -> List[str]:
        """Generate random Chinese-like sentences for performance testing."""
        sentences = []
        # Use characters that won't cause conflicts in day extraction
        chinese_chars = "我你他她它們的是在有這個那裡要去來住好車礙親子寵物友善"
        
        for _ in range(count):
            length = random.randint(10, max_length)
            sentence = ''.join(random.choice(chinese_chars) for _ in range(length))
            sentences.append(sentence)
        
        return sentences
    
    def test_performance_10000_sentences(self):
        """Test processing 10,000 sentences in ≤1 second."""
        sentences = self.generate_random_sentences(10000, 100)
        
        start_time = time.time()
        
        for sentence in sentences:
            extract_days(sentence)
            tokens = [sentence[i:i+2] for i in range(0, len(sentence), 2)]
            extract_filters(tokens)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert processing_time <= 1.0, f"Processing took {processing_time:.3f}s, should be ≤1.0s"
        print(f"Performance test passed: {processing_time:.3f}s for 10,000 sentences")


class TestEdgeCases:
    """Test various edge cases and special scenarios."""
    
    def test_mixed_language_input(self):
        """Test with mixed Chinese and English input."""
        result = extract_days("住2天 stay 3 days")
        assert result == 2
    
    def test_special_characters(self):
        """Test with special characters and punctuation."""
        assert extract_days("住2天！！！") == 2
        assert extract_days("住，2，天") == 2
    
    def test_whitespace_handling(self):
        """Test with various whitespace patterns."""
        assert extract_days("  住 2 天  ") == 2
        assert extract_days("住\t2\n天") == 2
    
    def test_partial_keyword_matches(self):
        """Test partial keyword matches in filters."""
        result = extract_filters(['停車位', '好停車場'])
        assert 'parking' in result
        assert len(result) == 1
    
    def test_complex_queries(self):
        """Test complex real-world query patterns."""
        queries = [
            "我想住兩天一夜，需要有停車場和親子設施的飯店",
            "預計待三天，要無障礙房間，可以帶寵物嗎？",
            "四日三夜家族旅行，車子要好停車",
            "住一晚就好，有沒有適合輪椅的房間"
        ]
        
        for query in queries:
            result = parse_query(query)
            assert isinstance(result, dict)
            assert 'days' in result
            assert 'filters' in result
            print(f"Query: {query[:20]}... -> {result}")


# Backward compatibility tests
class TestBackwardCompatibility:
    """Test that the refactored code maintains backward compatibility."""
    
    def test_public_api_functions(self):
        """Test that all public API functions still work."""
        # Test extract_days
        assert extract_days("住2天") == 2
        assert extract_days("半天") is None
        
        # Test extract_filters
        assert 'parking' in extract_filters(['停車'])
        assert extract_filters([]) == []
        
        # Test parse_query
        result = parse_query("住2天要停車")
        assert result['days'] == 2
        assert 'parking' in result['filters']
    
    def test_exception_classes(self):
        """Test that custom exception classes are still available."""
        with raises(DaysOutOfRangeError):
            extract_days("住20天")
        
        with raises(ParseConflictError):
            extract_days("住1天待5晚")


if __name__ == "__main__":
    main([__file__, "-v"])