"""Unit tests for rank_accommodations functionality - comprehensive acceptance criteria tests."""

import pytest
from unittest.mock import Mock
import pandas as pd
import geopandas as gpd

from src.innsight.services.accommodation_search_service import AccommodationSearchService
from src.innsight.config import AppConfig
from src.innsight.exceptions import NoAccommodationError


class TestRankAccommodationsService:
    """Test cases for rank_accommodations functionality - comprehensive acceptance criteria tests."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = Mock(spec=AppConfig)
        self.config.rating_weights = {
            'tier': 4.0,
            'rating': 2.0,
            'parking': 1.0,
            'wheelchair': 1.0,
            'kids': 1.0,
            'pet': 1.0
        }
        # Add new configuration properties
        self.config.default_isochrone_intervals = [15, 30, 60]
        self.config.max_score = 100
        self.config.validation_sample_size = 10
        self.config.validation_large_dataset_threshold = 100
        self.config.default_top_n = 10
        self.config.default_missing_score = 50
        self.config.max_tier_value = 3
        self.config.max_rating_value = 5
        self.service = AccommodationSearchService(self.config)

    def test_correct_filter_application_parking_only(self):
        """正確套用過濾條件 - Given DataFrame 內同時存在 parking=yes 與 parking=no 的住宿；
        When 呼叫 rank_accommodations(df, filters=["parking"])；
        Then 回傳結果所有列的 tags.parking 必為 "yes"。"""
        
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3, 4],
            'name': ['Hotel A', 'Hotel B', 'Hotel C', 'Hotel D'],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'no'},
                {'parking': 'no', 'wheelchair': 'yes'}, 
                {'parking': 'yes', 'wheelchair': 'yes'},
                {'parking': 'no', 'wheelchair': 'no'}
            ],
            'tier': [1, 2, 1, 0],
            'rating': [4.0, 3.5, 4.5, 3.0],
            'score': [75.0, 65.0, 85.0, 45.0]
        })
        
        result = self.service.rank_accommodations(accommodations_df, filters=["parking"])
        
        # All returned results must have parking='yes'
        for _, row in result.iterrows():
            assert row['tags']['parking'] == 'yes'
        
        # Should return 2 accommodations (osmid 1 and 3)
        assert len(result) == 2
        assert set(result['osmid'].tolist()) == {1, 3}

    def test_score_descending_order_with_specific_range(self):
        """依分數遞減排序 - Given 已算好 score 欄，其中最高分 92、最低分 55；
        When 不帶任何 filters 呼叫函式；
        Then 回傳列表第一筆 score ≥ 第二筆 ≥ … ≥ 最後一筆，且第一筆為 92，最後一筆為 55。"""
        
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3, 4, 5],
            'name': ['Hotel A', 'Hotel B', 'Hotel C', 'Hotel D', 'Hotel E'],
            'tags': [
                {'parking': 'yes'},
                {'parking': 'no'}, 
                {'parking': 'yes'},
                {'parking': 'no'},
                {'parking': 'yes'}
            ],
            'tier': [3, 1, 2, 0, 2],
            'rating': [5.0, 3.0, 4.0, 2.5, 4.5],
            'score': [92.0, 65.0, 78.0, 55.0, 85.0]  # Highest: 92, Lowest: 55
        })
        
        result = self.service.rank_accommodations(accommodations_df)
        
        # Check descending order
        scores = result['score'].tolist()
        assert scores == sorted(scores, reverse=True)
        
        # Check first and last scores
        assert result.iloc[0]['score'] == 92.0
        assert result.iloc[-1]['score'] == 55.0
        
        # Verify all scores are present
        assert len(result) == 5

    def test_top_n_limit(self):
        """筆數限制可調 - Given top_n=5 參數；
        When 資料表有 100 筆合格住宿；
        Then 函式只回傳 5 筆，且皆為分數前 5 名。"""
        
        # Create 100 accommodations with random scores
        import random
        random.seed(42)  # For reproducible results
        
        accommodations_data = []
        for i in range(100):
            accommodations_data.append({
                'osmid': i + 1,
                'name': f'Hotel {i+1}',
                'tags': {'parking': 'yes'},  # All have parking to ensure they're all eligible
                'tier': random.randint(0, 3),
                'rating': random.uniform(1.0, 5.0),
                'score': random.uniform(10.0, 100.0)
            })
        
        accommodations_df = gpd.GeoDataFrame(accommodations_data)
        
        result = self.service.rank_accommodations(accommodations_df, top_n=5)
        
        # Should return exactly 5 results
        assert len(result) == 5
        
        # Should be the top 5 by score
        all_scores = sorted(accommodations_df['score'].tolist(), reverse=True)
        top_5_scores = all_scores[:5]
        result_scores = result['score'].tolist()
        
        assert result_scores == top_5_scores

    def test_no_results_friendly_response_empty_dataframe(self):
        """無結果時友善回應 - Given filters 但資料皆不符合；
        When 呼叫函式；
        Then 拋 NoAccommodationError；絕不能崩潰。"""
        
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2],
            'name': ['Hotel A', 'Hotel B'],
            'tags': [
                {'parking': 'no', 'wheelchair': 'no'},  # Neither has required amenities
                {'parking': 'no', 'wheelchair': 'no'}
            ],
            'tier': [1, 2],
            'rating': [4.0, 3.5],
            'score': [75.0, 65.0]
        })
        
        # Should raise NoAccommodationError, not crash
        with pytest.raises(NoAccommodationError) as exc_info:
            self.service.rank_accommodations(accommodations_df, filters=["wheelchair", "parking"])
        
        assert "No accommodations match the specified filters" in str(exc_info.value)

    def test_no_results_empty_input(self):
        """無結果時友善回應 - Given 空的 DataFrame；
        When 呼叫函式；
        Then 拋 NoAccommodationError。"""
        
        empty_df = gpd.GeoDataFrame()
        
        with pytest.raises(NoAccommodationError) as exc_info:
            self.service.rank_accommodations(empty_df)
        
        assert "No accommodations available to rank" in str(exc_info.value)

    def test_null_value_tolerance(self):
        """缺值容忍 - Given 某筆資料缺少 tags.parking；
        When 過濾條件不含 parking；
        Then 函式應照常運行並包含該筆資料（不可因 None 觸發例外）。"""
        
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3],
            'name': ['Hotel A', 'Hotel B', 'Hotel C'],
            'tags': [
                {'wheelchair': 'yes'},  # Missing parking key
                {'parking': 'yes', 'wheelchair': 'yes'}, 
                {}  # Missing both keys
            ],
            'tier': [1, 2, 0],
            'rating': [4.0, 3.5, 3.0],
            'score': [75.0, 85.0, 55.0]
        })
        
        # Filter by wheelchair only (not parking), should work fine
        result = self.service.rank_accommodations(accommodations_df, filters=["wheelchair"])
        
        # Should return 2 accommodations (those with wheelchair='yes')
        assert len(result) == 2
        assert set(result['osmid'].tolist()) == {1, 2}
        
        # Should not crash due to missing parking values
        assert result.iloc[0]['score'] >= result.iloc[1]['score']  # Properly sorted

    def test_type_consistency_validation(self):
        """型別一致 - Given 成功回傳的結果；
        Then 每筆資料必含 name:str, score:float, tier:int；score 介於 0–100；tier 介於 0–3。"""
        
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3],
            'name': ['Hotel A', 'Hotel B', 'Hotel C'],
            'tags': [
                {'parking': 'yes'},
                {'parking': 'yes'}, 
                {'parking': 'yes'}
            ],
            'tier': [1, 2, 3],
            'rating': [4.0, 3.5, 5.0],
            'score': [75.0, 85.0, 95.0]
        })
        
        result = self.service.rank_accommodations(accommodations_df)
        
        for _, row in result.iterrows():
            # Check name is string or None
            assert isinstance(row['name'], (str, type(None)))
            
            # Check score is numeric and in range 0-100
            assert isinstance(row['score'], (int, float))
            assert 0 <= row['score'] <= 100
            
            # Check tier is int and in range 0-3
            assert isinstance(row['tier'], (int, float))
            assert 0 <= int(row['tier']) <= 3

    def test_type_validation_invalid_score_range(self):
        """Test validation catches invalid score ranges."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1],
            'name': ['Hotel A'],
            'tags': [{'parking': 'yes'}],
            'tier': [1],
            'rating': [4.0],
            'score': [150.0]  # Invalid: > 100
        })
        
        with pytest.raises(ValueError) as exc_info:
            self.service.rank_accommodations(accommodations_df)
        
        assert "score must be between 0-100" in str(exc_info.value)

    def test_type_validation_invalid_tier_range(self):
        """Test validation catches invalid tier ranges."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1],
            'name': ['Hotel A'],
            'tags': [{'parking': 'yes'}],
            'tier': [5],  # Invalid: > 3
            'rating': [4.0],
            'score': [75.0]
        })
        
        with pytest.raises(ValueError) as exc_info:
            self.service.rank_accommodations(accommodations_df)
        
        assert "tier must be between 0-3" in str(exc_info.value)

    def test_multiple_filters_integration(self):
        """Test multiple filters work correctly together."""
        accommodations_df = gpd.GeoDataFrame({
            'osmid': [1, 2, 3, 4],
            'name': ['Hotel A', 'Hotel B', 'Hotel C', 'Hotel D'],
            'tags': [
                {'parking': 'yes', 'wheelchair': 'yes', 'kids': 'yes'},  # Matches all
                {'parking': 'yes', 'wheelchair': 'no', 'kids': 'yes'},   # Missing wheelchair
                {'parking': 'no', 'wheelchair': 'yes', 'kids': 'yes'},   # Missing parking
                {'parking': 'yes', 'wheelchair': 'yes', 'kids': 'no'}    # Missing kids
            ],
            'tier': [3, 2, 1, 2],
            'rating': [5.0, 4.0, 4.5, 4.2],
            'score': [95.0, 80.0, 85.0, 82.0]
        })
        
        result = self.service.rank_accommodations(accommodations_df, filters=["parking", "wheelchair", "kids"])
        
        # Only Hotel A should match all three filters
        assert len(result) == 1
        assert result.iloc[0]['osmid'] == 1
        assert result.iloc[0]['score'] == 95.0

    def test_performance_10000_records(self):
        """效能 - Given 10 000 筆住宿資料、随機 0–4 個條件；
        When 單執行緒批次呼叫 rank_accommodations；
        Then 整體運行時間 ≤ 0.2 秒（開發機）。"""
        
        import time
        import random
        random.seed(42)  # For reproducible results
        
        # Create 10,000 accommodations
        accommodations_data = []
        for i in range(10000):
            # Randomly assign amenities to create realistic filtering scenarios
            tags = {}
            if random.random() > 0.5:
                tags['parking'] = 'yes' if random.random() > 0.3 else 'no'
            if random.random() > 0.5:
                tags['wheelchair'] = 'yes' if random.random() > 0.2 else 'no'
            if random.random() > 0.5:  
                tags['kids'] = 'yes' if random.random() > 0.4 else 'no'
            if random.random() > 0.5:
                tags['pet'] = 'yes' if random.random() > 0.6 else 'no'
                
            accommodations_data.append({
                'osmid': i + 1,
                'name': f'Hotel {i+1}',
                'tags': tags,
                'tier': random.randint(0, 3),
                'rating': random.uniform(1.0, 5.0),
                'score': random.uniform(10.0, 100.0)
            })
        
        accommodations_df = gpd.GeoDataFrame(accommodations_data)
        
        # Test multiple scenarios with different filter combinations
        test_scenarios = [
            [],  # No filters
            ['parking'],
            ['wheelchair', 'parking'],
            ['kids', 'pet'],
            ['parking', 'wheelchair', 'kids', 'pet']  # All filters
        ]
        
        start_time = time.time()
        
        # Run multiple calls to simulate batch processing
        for scenario in test_scenarios:
            try:
                result = self.service.rank_accommodations(accommodations_df, filters=scenario, top_n=50)
                # Basic validation that the function works
                assert isinstance(result, gpd.GeoDataFrame)
                assert len(result) <= 50
            except NoAccommodationError:
                # This is acceptable for some filter combinations
                pass
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete within 0.2 seconds
        assert total_time <= 0.2, f"Performance test failed: took {total_time:.3f} seconds, expected ≤ 0.2s"