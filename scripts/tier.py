import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from typing import List, Union
from shapely.geometry import Polygon


def assign_tier(df: pd.DataFrame, polygons: List[Union[Polygon, List[Polygon]]]) -> gpd.GeoDataFrame:
    """
    根據多邊形包含關係為點位分配等級。
    
    Args:
        df: 包含 'lat' 和 'lon' 欄位的 DataFrame
        polygons:
            多邊形列表，依據等級排序（較小的多邊形獲得較高等級）
            可以是 Polygon 或 List[Polygon]（自動取第一個）
            例如：[isochrones_15, isochrones_30, isochrones_60] 其中 isochrones_15 獲得 tier=3
    
    Returns:
        包含原始資料加上 'tier' 欄位和 Point 幾何的 GeoDataFrame
    """
    # 複製輸入的 DataFrame
    gdf = df.copy()
    
    # 處理 polygons 輸入，統一轉換為 Polygon 物件
    processed_polygons = []
    for polygon_input in polygons:
        if isinstance(polygon_input, (list, tuple)) and len(polygon_input) > 0:
            # 如果是列表（如 List[Polygon]），取第一個元素
            processed_polygons.append(polygon_input[0])
        else:
            # 已經是 Polygon
            processed_polygons.append(polygon_input)
    
    # 從 lat/lon 建立 Point 幾何
    geometry = [Point(lon, lat) for lat, lon in zip(df['lat'], df['lon'])]
    gdf = gpd.GeoDataFrame(gdf, geometry=geometry, crs='EPSG:4326')
    
    # 初始化 tier 欄位為 0（不在任何多邊形內）
    gdf['tier'] = 0
    
    # 對於每個點，找到它所屬的最高等級（最小多邊形）
    for idx, point in enumerate(gdf.geometry):
        highest_tier = 0
        
        # 檢查每個多邊形，從最高等級到最低等級
        for i, polygon in enumerate(processed_polygons):
            tier_value = len(processed_polygons) - i
            
            # 直接使用 Polygon 進行包含檢查（最簡潔的方式）
            if point.within(polygon):
                highest_tier = max(highest_tier, tier_value)
        
        gdf.iloc[idx, gdf.columns.get_loc('tier')] = highest_tier
    
    return gdf