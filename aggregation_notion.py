from notion_client import Client
from datetime import datetime

# Notion API 연결
notion = Client(auth="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")

# 데이터베이스 ID
ORIGINAL_DB_ID = "21fbb891ec338034a32af6e327c932a4"
SUMMARY_DB_ID = "21fbb891ec33800ab5cdfb1e21b4de8e"

def format_month_key(date_str):
    # Notion 날짜가 ISO 형식일 경우
    date = datetime.fromisoformat(date_str)
    return f"{date.year}년 {date.month}월"

def get_all_pages(db_id):
    results = []
    start_cursor = None
    while True:
        response = notion.databases.query(
            **{
                "database_id": db_id,
                "start_cursor": start_cursor
            } if start_cursor else {
                "database_id": db_id
            }
        )
        results.extend(response["results"])
        if response.get("has_more"):
            start_cursor = response["next_cursor"]
        else:
            break

    print(f"📄 총 {len(results)}개 페이지 불러옴")
    return results

def get_month_start_date(date_str: str) -> str:
    """
    ISO 날짜 문자열 (예: 2025-07-29) → '2025-07-01' 반환
    """
    dt = datetime.fromisoformat(date_str)
    return dt.replace(day=1).strftime("%Y-%m-%d")

def get_or_create_summary_page(title, task_type, category_prop, date_str):
    # 기존 항목 검색
    response = notion.databases.query(
        database_id=SUMMARY_DB_ID,
        filter={
            "property": "제목",
            "title": {"equals": title}
        }
    )
    if response["results"]:
        return response["results"][0]["id"]

    # 새 항목 생성
    props = {
        "제목": {
            "title": [
                {"type": "text", "text": {"content": title}}
            ]
        },
        "구분": {
            "select": {"name": task_type}
        },
        "월": {
            "date": {
                "start": get_month_start_date(date_str)
            }
        }
    }

    # 카테고리가 있는 경우에만 추가
    if category_prop.get("select"):
        props["카테고리"] = {
            "select": {"name": category_prop["select"]["name"]}
        }

    new_page = notion.pages.create(
        parent={"database_id": SUMMARY_DB_ID},
        properties=props
    )

    print("🧪 props 전달 내용:")
    import json
    print(json.dumps(props, indent=2, ensure_ascii=False))

    return new_page["id"]

def update_original_pages():
    pages = get_all_pages(ORIGINAL_DB_ID)
    for page in pages:
        page_id = page["id"]
        properties = page["properties"]

        # ✅ 1. 완료 여부 체크
        completed_status = properties.get("완료여부", {}).get("status", {})
        completed_value = completed_status.get("name")
        if completed_status.get("name") != "완료":
            continue  # 완료된 항목만 처리

        # ✅ 2. 날짜 / 구분 / 카테고리 가져오기
        date_prop = properties.get("날짜", {})
        category_prop = properties.get("카테고리", {})
        type_prop = properties.get("구분", {})

        if not date_prop.get("date") or not type_prop.get("select"):
            continue  # 날짜 또는 구분이 없으면 무시

        date_str = date_prop["date"]["start"]
        task_type = type_prop["select"]["name"]
        month_key = format_month_key(date_str)

        # ✅ 3. 요약 제목 구성
        if task_type == "일기":
            title = f"{month_key} - {task_type}"
        else:
            if not category_prop.get("select"):
                print(f"⏩ {page_id} → 완료여부: '{completed_value}' → 제외됨")
                continue  # 카테고리가 없는 경우 무시 (단, 일기 외에는 필수)
            category = category_prop["select"]["name"]
            title = f"{month_key} - {task_type} - {category}"

        # ✅ 4. 요약 페이지 생성 or 검색
        summary_page_id = get_or_create_summary_page(
            title, task_type, category_prop, date_str
        )

        # ✅ 5. 중복 관계 확인
        existing_relations = properties.get("요약", {}).get("relation", [])
        already_linked = any(rel["id"] == summary_page_id for rel in existing_relations)
        if already_linked:
            continue

        updated_relations = existing_relations + [{"id": summary_page_id}]

        # ✅ 6. 관계형 속성 업데이트
        notion.pages.update(
            page_id=page["id"],
            properties={
                "요약": {
                    "relation": updated_relations
                }
            }
        )


if __name__ == "__main__":
    update_original_pages()
    print("✅ 요약 관계 업데이트 완료")
