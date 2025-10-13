import os
import re
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup

# DB 모델 import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.model import GetchaReview, create_tables_if_not_exist
from db.connection import session_scope

# =========================
# 설정
# =========================
BASE_LIST_URL = "https://web.getcha.kr/community/owner-review?page={page}"
BASE_DETAIL_URL = "https://web.getcha.kr/community/owner-review/{rid}?topic={topic}&page=1&sort=LATEST"
TOPIC_ID_DEFAULT = 11

LIST_SLEEP = 0.25
DETAIL_SLEEP = 0.15
MAX_WORKERS = 8
REQ_TIMEOUT = 15

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GetchaCrawler/1.0)",
}

# 세션 + 재시도
_session = requests.Session()
_retry = Retry(
    total=5, backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"])
)
_session.mount("https://", HTTPAdapter(max_retries=_retry))
_session.headers.update(HEADERS)

# 정규식 사전 컴파일
RE_ID = re.compile(r'\\"id_contents\\":(\d+)')
RE_TPAGE = re.compile(r'\\"totalPage\\":(\d+)')
RE_TCOUNT = re.compile(r'\\"totalContentsCount\\":(\d+)')
RE_CPAGE = re.compile(r'\\"currentPage\\":(\d+)')
RE_DATALIST = re.compile(r'\{\\"dataList\\":')

# =========================
# 공통 유틸
# =========================
def _get(url: str) -> str:
    r = _session.get(url, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    return r.text

def _iter_scripts(html: str) -> Iterable[str]:
    soup = BeautifulSoup(html, "html.parser")
    for s in soup.find_all("script"):
        if s.string:
            yield s.string

# =========================
# 리스트 페이지
# =========================
def _parse_list(html: str, fallback_page: int) -> Optional[Dict[str, Any]]:
    for sc in _iter_scripts(html):
        if "items" in sc and "id_contents" in sc:
            ids = [int(m) for m in RE_ID.findall(sc)]
            if not ids:
                continue
            page_info = {
                "currentPage": int(RE_CPAGE.search(sc).group(1)) if RE_CPAGE.search(sc) else fallback_page,
                "totalPage": int(RE_TPAGE.search(sc).group(1)) if RE_TPAGE.search(sc) else None,
                "totalContentsCount": int(RE_TCOUNT.search(sc).group(1)) if RE_TCOUNT.search(sc) else None,
            }
            return {"ids": ids, "page": page_info}
    return None

def fetch_list_page(page: int) -> Optional[Dict[str, Any]]:
    try:
        html = _get(BASE_LIST_URL.format(page=page))
        return _parse_list(html, fallback_page=page)
    except Exception as e:
        print(f"[LIST] {page} 실패: {e}")
        return None

def gather_ids(start_page: int = 1, end_page: Optional[int] = None) -> Dict[str, Any]:
    """start_page부터 end_page까지 id 수집. end_page=None이면 전체."""
    first = fetch_list_page(start_page)
    if not first or "page" not in first:
        raise RuntimeError("첫 페이지 파싱 실패")

    total_pages = first["page"]["totalPage"] or start_page
    total_count = first["page"]["totalContentsCount"] or 0
    if end_page is None:
        end_page = total_pages
    else:
        end_page = min(end_page, total_pages)

    ids: List[int] = []
    ids.extend(first["ids"])
    print(f"[LIST] {start_page} 수집: {len(first['ids'])}개")

    for p in range(start_page + 1, end_page + 1):
        time.sleep(LIST_SLEEP)
        data = fetch_list_page(p)
        if not data or not data.get("ids"):
            print(f"[LIST] {p} 비어있음/실패 → 중단")
            break
        ids.extend(data["ids"])
        print(f"[LIST] {p} 수집: {len(data['ids'])}개")

    return {"ids": ids, "meta": {"total_pages": total_pages, "total_count": total_count, "range": (start_page, end_page)}}

# =========================
# 상세 페이지
# =========================
def _parse_detail(html: str) -> Dict[str, Any]:
    for sc in _iter_scripts(html):
        if "dataList" in sc and "reviewDetails" in sc:
            m = RE_DATALIST.search(sc)
            if not m: 
                continue
            start = m.start()
            brace = 0
            end = None
            for i, ch in enumerate(sc[start:], start):
                if ch == "{":
                    brace += 1
                elif ch == "}":
                    brace -= 1
                    if brace == 0:
                        end = i + 1
                        break
            if not end:
                continue

            raw = sc[start:end].replace('\\"', '"').replace('\\\\', '\\')
            data = json.loads(raw)
            vc = (data.get("dataList") or {}).get("viewContent") or {}

            out: Dict[str, Any] = {
                "id_contents": vc.get("id_contents"),
                "title": vc.get("title"),
                "contents": vc.get("contents"),
                "reply_cnt": vc.get("reply_cnt"),
                "like_cnt": vc.get("like_cnt"),
                "view_cnt": vc.get("view_cnt"),
                "created": vc.get("created"),
                "images": [img.get("url") for img in (vc.get("images") or [])],
            }

            owner = (vc.get("detail") or {}).get("owner_review") or {}
            out["price"] = owner.get("price")
            out["reviewDetails"] = owner.get("reviewDetails", [])

            for rd in out["reviewDetails"]:
                item = (rd.get("review_item") or "").strip()
                if not item:
                    continue
                out[f"{item}_평점"] = rd.get("rating")
                out[f"{item}_코멘트"] = rd.get("review_detail")

            car = owner.get("carInfo") or {}
            out.update({
                "brand_name": car.get("brand_name"),
                "model_name": car.get("model_name"),
                "grade_name": car.get("grade_name"),
                "year": car.get("year"),
            })

            user = vc.get("user") or {}
            out.update({"user_nickname": user.get("nickname"), "user_lv": user.get("lv")})
            return out
    return {}

def fetch_detail(rid: int, topic_id: int = TOPIC_ID_DEFAULT) -> Dict[str, Any]:
    try:
        html = _get(BASE_DETAIL_URL.format(rid=rid, topic=topic_id))
        return _parse_detail(html)
    except Exception as e:
        print(f"[DETAIL] {rid} 실패: {e}")
        return {}

# =========================
# DB 저장
# =========================
def _safe_int(v):
    try:
        return int(str(v).strip()) if v is not None and str(v).strip() else None
    except:
        return None

def _safe_float(v):
    try:
        return float(str(v).strip()) if v is not None and str(v).strip() else None
    except:
        return None

def map_to_model(review: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id_contents": review.get("id_contents"),
        "title": review.get("title"),
        "created": review.get("created"),
        "manufacturer": review.get("brand_name"),
        "model_group": review.get("model_name"),
        "grade": review.get("grade_name"),
        "model_year": _safe_int(review.get("year")),
        "price": _safe_int(review.get("price")),
        "rating_total": _safe_float(review.get("총점_평점")),
        "rating_design": _safe_float(review.get("디자인_평점")),
        "rating_performance": _safe_float(review.get("성능_평점")),
        "rating_option": _safe_float(review.get("옵션_평점")),
        "rating_maintenance": _safe_float(review.get("유지관리_평점")),
        "comment_total": review.get("총점_코멘트"),
        "comment_design": review.get("디자인_코멘트"),
        "comment_performance": review.get("성능_코멘트"),
        "comment_option": review.get("옵션_코멘트"),
        "comment_maintenance": review.get("유지관리_코멘트"),
        "crawled_at": datetime.now(),
    }

def save_to_db(reviews: List[Dict[str, Any]]) -> int:
    if not reviews:
        return 0

    review_ids = [r.get("id_contents") for r in reviews if r.get("id_contents")]
    try:
        with session_scope() as sess:
            existing = sess.query(GetchaReview).filter(GetchaReview.id_contents.in_(review_ids)).all()
            existing_map = {e.id_contents: e for e in existing}

            new_cnt = 0
            upd_cnt = 0
            for data in reviews:
                rid = data.get("id_contents")
                if not rid:
                    continue
                row = map_to_model(data)
                if rid in existing_map:
                    obj = existing_map[rid]
                    for k, v in row.items():
                        setattr(obj, k, v)
                    upd_cnt += 1
                else:
                    sess.add(GetchaReview(**row))
                    new_cnt += 1

            sess.commit()
            print(f"[DB] 신규 {new_cnt}건, 업데이트 {upd_cnt}건")
            return new_cnt + upd_cnt
    except Exception as e:
        print(f"[DB] 실패: {e}")
        return 0

# =========================
# 전체 실행
# =========================
def execute_full_crawling(start_page: int = 1, end_page: Optional[int] = None, topic_id: int = TOPIC_ID_DEFAULT) -> List[Dict[str, Any]]:
    print("=== Getcha 리뷰 크롤링 시작 ===")

    # 기존 저장 ID
    existing_ids: set[int] = set()
    try:
        with session_scope() as sess:
            existing_ids = {row[0] for row in sess.query(GetchaReview.id_contents).all()}
        print(f"[INIT] 기존 저장 리뷰: {len(existing_ids)}개")
    except Exception as e:
        print(f"[INIT] 기존 리뷰 조회 실패: {e}")

    # 리스트 수집
    ids_pack = gather_ids(start_page=start_page, end_page=end_page)
    ids = ids_pack["ids"]
    meta = ids_pack["meta"]
    print(f"[LIST] 수집 범위: {meta['range'][0]}~{meta['range'][1]}, 수집 ID: {len(ids)}개 (총페이지={meta['total_pages']}, 총리뷰={meta['total_count']})")

    # 상세 수집 (기존 제외) + 병렬화
    targets = [rid for rid in ids if rid not in existing_ids]
    print(f"[DETAIL] 신규 대상: {len(targets)}개 (건너뛰기 {len(ids) - len(targets)}개)")

    results: List[Dict[str, Any]] = []
    batch: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = []
        for rid in targets:
            futs.append(ex.submit(fetch_detail, rid, topic_id))
            time.sleep(DETAIL_SLEEP)  # 온건한 간격

        for i, fut in enumerate(as_completed(futs), 1):
            det = fut.result()
            if det and det.get("id_contents"):
                batch.append(det)
            if len(batch) >= 100:
                save_to_db(batch)
                results.extend(batch)
                batch.clear()
                print(f"[PROG] {i}건 처리")

    if batch:
        save_to_db(batch)
        results.extend(batch)

    print(f"[DONE] 총 {len(results)}건 저장")
    return results

def main():
    create_tables_if_not_exist()
    try:
        data = execute_full_crawling(start_page=1, end_page=None, topic_id=TOPIC_ID_DEFAULT)
        print(f"수집 완료: {len(data)}건")
    except Exception as e:
        print(f"실행 실패: {e}")

if __name__ == "__main__":
    main()
