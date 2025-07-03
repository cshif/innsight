import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from typing import List, Union
from shapely.geometry import Polygon

# 預設緩衝距離，用於處理邊界點
DEFAULT_BUFFER = 1e-5


class TierError(Exception):
    """Tier 分配過程中的錯誤"""
    pass


def assign_tier(
        df: pd.DataFrame,
        polygons: List[Union[Polygon, List[Polygon]]],
        buffer: float = DEFAULT_BUFFER
) -> gpd.GeoDataFrame:
    """
    根據多邊形包含關係為點位分配等級。
    
    Args:
        df: 包含 'lat' 和 'lon' 欄位的 DataFrame
        polygons:
            多邊形列表，依據等級排序（較小的多邊形獲得較高等級）
            可以是 Polygon 或 List[Polygon]（自動取第一個）
            例如：[isochrones_15, isochrones_30, isochrones_60] 其中 isochrones_15 獲得 tier=3
        buffer: 對多邊形進行緩衝的距離，用於處理邊界點（預設 DEFAULT_BUFFER = 1e-5）
    
    Returns:
        包含原始資料加上 'tier' 欄位和 Point 幾何的 GeoDataFrame
    """
    # 複製輸入的 DataFrame
    gdf = df.copy()
    
    # 驗證必要欄位是否存在
    if 'lat' not in df.columns or 'lon' not in df.columns:
        raise TierError("DataFrame 必須包含 'lat' 和 'lon' 欄位")
    
    # 檢查是否有缺失的緯度或經度值
    missing_lat = df['lat'].isna().any()
    missing_lon = df['lon'].isna().any()
    
    if missing_lat or missing_lon:
        missing_info = []
        if missing_lat:
            missing_info.append("緯度")
        if missing_lon:
            missing_info.append("經度")
        raise TierError(f"缺少{' 或 '.join(missing_info)}")
    
    # 處理 polygons 輸入，統一轉換為 Polygon 物件
    processed_polygons = []
    for i, polygon_input in enumerate(polygons):
        try:
            if isinstance(polygon_input, (list, tuple)):
                if len(polygon_input) == 0:
                    raise TierError(f"第{i+1}層多邊形格式不正確：列表不能為空")
                # 如果是列表（如 List[Polygon]），取第一個元素
                polygon = polygon_input[0]
                # 驗證列表中的第一個元素是否為 Polygon
                if not isinstance(polygon, Polygon):
                    raise TierError(f"第{i+1}層多邊形格式不正確：列表中的元素必須是 Polygon 物件，實際為 {type(polygon).__name__}")
            else:
                # 應該是 Polygon
                polygon = polygon_input
                # 驗證是否為 Polygon
                if not isinstance(polygon, Polygon):
                    raise TierError(f"第{i+1}層多邊形格式不正確：必須是 Polygon 物件，實際為 {type(polygon).__name__}")
            
            # 如果指定了緩衝距離，對多邊形進行緩衝
            if buffer > 0:
                polygon = polygon.buffer(buffer)
            
            processed_polygons.append(polygon)
            
        except TierError:
            # 重新拋出 TierError
            raise
        except (AttributeError, TypeError) as e:
            # 處理其他可能的類型錯誤
            raise TierError(f"第{i+1}層多邊形格式不正確：{str(e)}")
    
    # 建立 GeoDataFrame
    geometry = [Point(lon, lat) for lat, lon in zip(df['lat'], df['lon'])]
    gdf = gpd.GeoDataFrame(gdf, geometry=geometry, crs='EPSG:4326')
    
    # 初始化 tier 欄位為 0
    gdf['tier'] = 0
    
    # 如果是空 DataFrame，直接返回
    if len(df) == 0:
        return gdf
    
    # 性能優化：對於重複座標，只計算一次
    # 創建座標到索引的映射
    coord_key = df['lat'].round(8).astype(str) + ',' + df['lon'].round(8).astype(str)
    unique_coords = coord_key.drop_duplicates()
    
    # 創建唯一座標的 tier 映射
    coord_to_tier = {}
    
    # 只對唯一座標進行 tier 計算
    for coord in unique_coords:
        lat_str, lon_str = coord.split(',')
        lat, lon = float(lat_str), float(lon_str)
        point = Point(lon, lat)
        
        highest_tier = 0
        # 檢查每個多邊形，從最高等級到最低等級
        for i, polygon in enumerate(processed_polygons):
            tier_value = len(processed_polygons) - i
            
            # 直接使用 Polygon 進行包含檢查
            if point.within(polygon):
                highest_tier = max(highest_tier, tier_value)
        
        coord_to_tier[coord] = highest_tier
    
    # 使用預計算的 tier 值
    gdf['tier'] = coord_key.map(coord_to_tier)
    
    return gdf