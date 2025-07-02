import pytest
import pandas as pd
from shapely.geometry import Point, Polygon
from scripts.tier import assign_tier


def create_test_polygons():
    """建立測試多邊形，模擬 get_isochrones() 回傳格式。"""
    # 根據預期測試結果建立多邊形：
    # A (26.7, 127.88) 應該在 tier 3 (僅在15分鐘多邊形內)
    # B (26.8, 127.88) 應該在 tier 2 (在30分鐘多邊形內，但不在15分鐘內)
    # C (27.0, 127.88) 應該在 tier 1 (在60分鐘多邊形內，但不在30分鐘內)
    # D (28.0, 127.88) 應該在 tier 0 (不在任何多邊形內)
    
    # 建立15分鐘多邊形 (tier 3) - 應該只包含點 A
    poly15_coords = [
        (127.8, 26.65),
        (127.96, 26.65),
        (127.96, 26.75),
        (127.8, 26.75),
        (127.8, 26.65)
    ]
    isochrones_15 = [Polygon(poly15_coords)]  # 模擬 get_isochrones 回傳格式
    
    # 建立30分鐘多邊形 (tier 2) - 應該包含點 A 和 B
    poly30_coords = [
        (127.8, 26.65),
        (127.96, 26.65),
        (127.96, 26.85),
        (127.8, 26.85),
        (127.8, 26.65)
    ]
    isochrones_30 = [Polygon(poly30_coords)]  # 模擬 get_isochrones 回傳格式
    
    # 建立60分鐘多邊形 (tier 1) - 應該包含點 A、B 和 C
    poly60_coords = [
        (127.8, 26.65),
        (127.96, 26.65),
        (127.96, 27.05),
        (127.8, 27.05),
        (127.8, 26.65)
    ]
    isochrones_60 = [Polygon(poly60_coords)]  # 模擬 get_isochrones 回傳格式
    
    return isochrones_15, isochrones_30, isochrones_60


def test_assign_tier():
    """測試 assign_tier 函數的指定測試數據。"""
    # 建立指定的測試 DataFrame
    df = pd.DataFrame([
        {"name": "A", "lat": 26.7, "lon": 127.88},   # 在 15 min 圈內
        {"name": "B", "lat": 26.8, "lon": 127.88},   # 在 30 min 圈內、但不在 15 min
        {"name": "C", "lat": 27.0, "lon": 127.88},   # 在 60 min 圈內、但不在 30 min
        {"name": "D", "lat": 28.0, "lon": 127.88},   # 不在任何圈
    ])
    
    # 建立測試多邊形 (模擬 get_isochrones 回傳格式)
    isochrones_15, isochrones_30, isochrones_60 = create_test_polygons()
    
    # 呼叫 assign_tier 函數 (就像 main.py 中的用法)
    gdf = assign_tier(df, [isochrones_15, isochrones_30, isochrones_60])
    
    # 測試 1: gdf 有 tier 欄位，長度與原 df 相同 (4)
    assert 'tier' in gdf.columns, "GeoDataFrame 應該有 'tier' 欄位"
    assert len(gdf) == len(df) == 4, f"GeoDataFrame 長度應該為 4，實際為 {len(gdf)}"
    
    # 測試 2: gdf["tier"].tolist() == [3, 2, 1, 0]
    expected_tiers = [3, 2, 1, 0]
    actual_tiers = gdf["tier"].tolist()
    assert actual_tiers == expected_tiers, f"預期 tier 為 {expected_tiers}，實際為 {actual_tiers}"
    
    # 測試 3: gdf.geometry 欄為 Point 類型，gdf.crs.to_epsg() == 4326
    assert all(isinstance(geom, Point) for geom in gdf.geometry), "所有幾何應該都是 Point 類型"
    assert gdf.crs.to_epsg() == 4326, f"CRS 應該為 EPSG:4326，實際為 {gdf.crs.to_epsg()}"
    
    # 額外測試：確認原始數據被保留
    for col in df.columns:
        pd.testing.assert_series_equal(gdf[col], df[col], check_names=True)


def test_assign_tier_empty_dataframe():
    """測試 assign_tier 處理空 DataFrame。"""
    df = pd.DataFrame(columns=["name", "lat", "lon"])
    isochrones_15, isochrones_30, isochrones_60 = create_test_polygons()
    
    gdf = assign_tier(df, [isochrones_15, isochrones_30, isochrones_60])
    
    assert len(gdf) == 0, "空 DataFrame 應該返回空 GeoDataFrame"
    assert 'tier' in gdf.columns, "空 GeoDataFrame 仍應該有 'tier' 欄位"
    assert gdf.crs.to_epsg() == 4326, "CRS 應該為 EPSG:4326"


def test_assign_tier_single_polygon():
    """測試 assign_tier 處理單一多邊形。"""
    df = pd.DataFrame([
        {"name": "A", "lat": 26.7, "lon": 127.88},  # 在 isochrones_15 內
        {"name": "B", "lat": 28.0, "lon": 127.88},  # 在所有多邊形外
    ])
    
    isochrones_15, _, _ = create_test_polygons()
    
    gdf = assign_tier(df, [isochrones_15])
    
    expected_tiers = [1, 0]  # 第一個點在內，第二個在外
    actual_tiers = gdf["tier"].tolist()
    assert actual_tiers == expected_tiers, f"預期 tier 為 {expected_tiers}，實際為 {actual_tiers}"


if __name__ == "__main__":
    pytest.main([__file__])