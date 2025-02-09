import json
import csv

# 读取 JSON 文件
def json_to_csv(json_file, csv_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 选择需要的字段
    fieldnames = [
        "id", "title", "circle_name", "nsfw", "release", "dl_count", "price", 
        "review_count", "rate_count", "rate_average_2dp", "has_subtitle", "duration", "source_url",
        "vas", "tags", "rank"
    ]
    
    # 处理 JSON 数据
    rows = []
    for item in data:
        row = {
            "id": item.get("id"),
            "title": item.get("title"),
            "circle_name": item.get("circle", {}).get("name"),
            "nsfw": item.get("nsfw"),
            "release": item.get("release"),
            "dl_count": item.get("dl_count"),
            "price": item.get("price"),
            "review_count": item.get("review_count"),
            "rate_count": item.get("rate_count"),
            "rate_average_2dp": item.get("rate_average_2dp"),
            "has_subtitle": item.get("has_subtitle"),
            "duration": item.get("duration"),
            "source_url": item.get("source_url"),
            "vas": ", ".join([va["name"] for va in item.get("vas", [])]),
            "tags": ", ".join([tag["name"] for tag in item.get("tags", [])]),
            "rank": ", ".join([f"{r['term']} ({r['category']}): {r['rank']}" for r in item.get("rank", [])] if isinstance(item.get("rank"), list) else ""),
        }
        rows.append(row)
    
    # 写入 CSV
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"CSV 文件已生成: {csv_file}")


def main():
    json_to_csv("all_works.json", "output.csv")


if __name__ == "__main__":
    main()