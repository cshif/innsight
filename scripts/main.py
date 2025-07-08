import os, time
from typing import List

from nominatim_client import NominatimClient, NominatimError
from overpass_client import fetch_overpass
from ors_client import get_isochrones_by_minutes
from tier import assign_tier
from parser import parse_query, extract_location_from_query
import pandas as pd

# 可配置的時間間隔（分鐘）
DEFAULT_TIME_INTERVALS = [15, 30, 60]


def get_tier_name(tier: int, intervals: List[int] = None) -> str:
    """根據等級值生成顯示名稱。"""
    if intervals is None:
        intervals = DEFAULT_TIME_INTERVALS
        
    if tier == 0:
        return f"{max(intervals)}分鐘外"
    elif 1 <= tier <= len(intervals):
        minutes = intervals[-tier]  # tier 3 -> intervals[0], tier 2 -> intervals[1]
        return f"{minutes}分鐘內"
    else:
        return f"Tier {tier}"


def main(argv: list[str] | None = None) -> None:  # noqa: D401
    import argparse

    parser = argparse.ArgumentParser(description="旅宿推薦系統")
    parser.add_argument("--query", help="請輸入主行程、要去的天數及特殊需求等")
    parser.add_argument(
        "--intervals",
        nargs="+",
        type=int,
        default=DEFAULT_TIME_INTERVALS,
        help=f"請輸入時間間隔 (單位：分鐘) (default: {DEFAULT_TIME_INTERVALS})"
    )

    args = parser.parse_args(argv)

    # 解析中文查詢（如果有的話）
    parsed_query = None
    if args.query:
        parsed_query = parse_query(args.query)
        print("\n=== 查詢解析結果 ===")
        
        if parsed_query.get('days'):
            print(f"住宿天數: {parsed_query['days']} 天")
            if parsed_query['days'] >= 7:
                print("  → 建議尋找長住優惠")
            elif parsed_query['days'] <= 2:
                print("  → 短期住宿，可考慮市中心位置")
        
        if parsed_query.get('filters'):
            print(f"篩選需求: {', '.join(parsed_query['filters'])}")
            filter_descriptions = {
                'parking': '需要停車位',
                'wheelchair': '需要無障礙設施',
                'kids': '親子友善',
                'pet': '允許寵物'
            }
            for f in parsed_query['filters']:
                if f in filter_descriptions:
                    print(f"  → {filter_descriptions[f]}")
        
        if parsed_query.get('poi'):
            print(f"興趣點類型: {', '.join(parsed_query['poi'])}")
            poi_descriptions = {
                'sightseeing': '觀光景點',
                'culture': '文化體驗',
                'historical': '歷史遺跡',
                'nature': '自然景觀',
                'food': '美食',
                'shopping': '購物',
                'entertainment': '娛樂',
                'transportation': '交通便利'
            }
            for poi in parsed_query['poi']:
                if poi in poi_descriptions:
                    print(f"  → {poi_descriptions[poi]}")
        
        print("=" * 50)

    # 必須提供查詢參數
    if not args.query:
        parser.error("請提供 --query 參數")
    
    # 從查詢中提取地點或景點
    poi = extract_location_from_query(parsed_query, args.query)
    if not poi:
        parser.error("無法從查詢中識別地點，請在 --query 中包含地點")
    
    print(f"\n=== 從查詢中識別地點 ===")
    print(f"識別到地點: {poi}")
    print("=" * 50)

    api_endpoint = os.getenv("API_ENDPOINT")
    if not api_endpoint:
        parser.error("API_ENDPOINT environment variable not set")

    nominatim_client = NominatimClient(api_endpoint)
    try:
        data = nominatim_client.geocode(poi)
        if not data:
            parser.error(f"No results found for {poi}")
        lat = float(data[0][0])
        lon = float(data[0][1])
        query = f"""
            [out:json][timeout:25];

            // 1. 找 100 公尺內水族館
            nwr(around:100,{lat},{lon})["tourism"="aquarium"]->.aquarium;

            // 2. 直接查 admin_level=7 area（可根據需要調整 admin_level）
            is_in({lat},{lon})->.areas;
            area.areas[boundary="administrative"][admin_level=7]->.mainArea;

            // 3. 取這個 area 對應的 relation
            rel(pivot.mainArea)->.mainRel;

            // 4. 找主行政區的邊界 ways
            way(r.mainRel)->.borderWays;

            // 5. 找和主行政區接壤的其他 admin_level=7 行政區（即鄰居）
            rel(bw.borderWays)[boundary="administrative"][admin_level=7]->.neighborRels;

            // 6. relation 轉 area id
            rel.neighborRels->.tmpRels;
            (.tmpRels; map_to_area;)->.neighborAreas;

            // 7. 查所有鄰近 area 內的旅宿
            nwr(area.neighborAreas)[tourism~"hotel|guest_house|hostel|motel|apartment|camp_site|caravan_site"];
            out center;
            """
        elements = fetch_overpass(query)
    except NominatimError as exc:
        parser.error(str(exc))
    else:
        rows = []
        for el in elements:
            # 1) 抓座標：node 直接用 lat/lon；way/relation 用 center
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")

            # 2) 基本欄位 ( + tags 攤平)
            row = {
                "osmid": el["id"],
                "osmtype": el["type"],
                "lat": lat,
                "lon": lon,
                # **el.get("tags", {})  # 把 tags 字典整個拆進來
                "tourism": el.get("tags", {}).get("tourism"),
                "name": el.get("tags", {}).get("name"),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        print(data)
        print(df)
        print(f"共抓到 {len(elements)} 筆")

        lat_str, lon_str = data[0]
        coord: tuple[float, float] = (float(lon_str), float(lat_str))

        # 第一次獲取等時圈
        print("=== 第一次獲取等時圈 ===")
        print(f"使用時間間隔: {args.intervals} 分鐘")
        start = time.perf_counter()
        isochrones_list = get_isochrones_by_minutes(coord, args.intervals)
        t1 = time.perf_counter() - start
        
        interval_info = " | ".join(
            [f"{interval}分鐘={len(iso)}" for interval,
            iso in zip(args.intervals, isochrones_list)]
        )
        print(f"取得等時圈: {interval_info}")
        print(f"第一次獲取花了 {t1:.4f}s")
        
        # 顯示快取資訊
        cache_info = get_isochrones_by_minutes.cache_info()
        print(f"快取資訊: 共 {cache_info['size']} 個項目")
        
        # 第二次獲取（測試快取）
        print("\n=== 第二次獲取等時圈（測試快取）===")
        start = time.perf_counter()
        # 重複相同的調用來測試快取效果（不儲存結果）
        get_isochrones_by_minutes(coord, args.intervals)
        t2 = time.perf_counter() - start
        
        print(f"第二次獲取花了 {t2:.4f}s（應該很快，因為有快取）")
        print(f"速度提升: {t1/t2:.1f}x 倍")
        
        # 最終快取資訊
        cache_info = get_isochrones_by_minutes.cache_info()
        print(f"最終快取資訊: 共 {cache_info['size']} 個項目")
        for key, (polygon_count, timestamp) in cache_info['items'].items():
            age_hours = (time.time() - timestamp) / 3600
            print(f"  - {polygon_count} 個多邊形，{age_hours:.3f} 小時前")

        if isochrones_list and all(isochrones_list) and len(df) > 0:
            # 使用 assign_tier 為旅宿分配等級（直接傳入 List[Polygon]，函數會自動取第一個）
            gdf = assign_tier(df, isochrones_list)
            
            print("\n旅宿分級結果:")
            print(gdf[['name', 'tourism', 'lat', 'lon', 'tier']].to_string())
            
            # 統計各等級數量
            tier_counts = gdf['tier'].value_counts().sort_index()
            print(f"\n各等級統計:")
            for tier, count in tier_counts.items():
                tier_name = get_tier_name(tier, args.intervals)
                print(f"  {tier_name}: {count} 家")
        else:
            print("無法獲取完整等時圈或無旅宿資料")


if __name__ == "__main__":  # pragma: no cover
    main()