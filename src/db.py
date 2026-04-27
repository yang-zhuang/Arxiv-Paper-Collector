"""MongoDB 数据库模块 — 与 ACL Anthology Downloader 共用 acl_anthology.papers 集合"""

from datetime import datetime, timezone

from pymongo import MongoClient, UpdateOne

DEFAULT_URI = "mongodb://localhost:27017"
DB_NAME = "acl_anthology"
COLLECTION = "papers"

_client = None
_db = None


def get_db(uri: str = DEFAULT_URI):
    """获取 MongoDB 连接（懒加载单例）"""
    global _client, _db
    if _db is None:
        _client = MongoClient(uri)
        _db = _client[DB_NAME]
        _db[COLLECTION].create_index("pdf_url", unique=True)
        _db[COLLECTION].create_index([("category", 1), ("year", 1)])
        _db[COLLECTION].create_index("source")
        _db[COLLECTION].create_index("status")
    return _db


def upsert_papers_batch(db, papers: list[dict], source: str = "arxiv") -> int:
    """批量写入论文，已存在则更新。返回写入数量。"""
    ops = []
    now = datetime.now(timezone.utc)
    for paper in papers:
        ops.append(UpdateOne(
            {"pdf_url": paper["pdf_url"]},
            {"$set": {
                "title": paper["title"],
                "category": paper["category"],
                "year": paper["year"],
                "abstract": paper.get("abstract"),
                "arxiv_id": paper.get("arxiv_id"),
                "published": paper.get("published"),
                "authors": paper.get("authors"),
                "source": source,
                "updated_at": now,
            }, "$setOnInsert": {
                "status": "pending",
                "pdf_file": None,
                "error_message": None,
                "created_at": now,
            }},
            upsert=True,
        ))
    if not ops:
        return 0
    result = db[COLLECTION].bulk_write(ops)
    return result.modified_count + result.upserted_count


def get_pending_papers(db, category: str = None, start_year: int = None,
                       end_year: int = None, source: str = "arxiv") -> list[dict]:
    """获取待下载的论文（status 为 pending 或 failed）"""
    query = {"status": {"$in": ["pending", "failed"]}, "source": source}
    if category:
        query["category"] = category
    if start_year and end_year:
        query["year"] = {"$gte": start_year, "$lte": end_year}
    elif start_year:
        query["year"] = {"$gte": start_year}
    elif end_year:
        query["year"] = {"$lte": end_year}
    return list(db[COLLECTION].find(query))


def mark_completed(db, pdf_url: str, pdf_file: str):
    """标记论文下载完成"""
    db[COLLECTION].update_one(
        {"pdf_url": pdf_url},
        {"$set": {
            "status": "completed",
            "pdf_file": pdf_file,
            "error_message": None,
            "updated_at": datetime.now(timezone.utc),
        }},
    )


def mark_failed(db, pdf_url: str, error_message: str):
    """标记论文下载失败"""
    db[COLLECTION].update_one(
        {"pdf_url": pdf_url},
        {"$set": {
            "status": "failed",
            "error_message": error_message,
            "updated_at": datetime.now(timezone.utc),
        }},
    )


def get_stats(db, category: str = None, source: str = "arxiv") -> dict:
    """获取下载统计"""
    match = {"source": source}
    if category:
        match["category"] = category
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    return {doc["_id"]: doc["count"] for doc in db[COLLECTION].aggregate(pipeline)}


def get_existing_papers(db, category: str, start_year: int, end_year: int,
                        source: str = "arxiv", status: str = "completed") -> dict[str, str]:
    """获取指定类别和年份范围内的论文，返回 {pdf_url: title}"""
    query = {
        "source": source,
        "category": category,
        "year": {"$gte": start_year, "$lte": end_year}
    }
    if status is not None:
        query["status"] = status
    return {doc["pdf_url"]: doc.get("title", "") for doc in db[COLLECTION].find(query, {"pdf_url": 1, "title": 1, "_id": 0})}


def close():
    """关闭 MongoDB 连接"""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
