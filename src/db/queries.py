"""
Funding Intelligence Agent — SQL 쿼리 상수.

entity_store.py와 interface/handlers에서 사용.
"""

# Curated View: Eligibility Filter 적용된 기회 목록
CURATED_VIEW_SQL = """
SELECT
    o.id, o.status, o.deadline_at, o.days_left,
    o.budget_amount, o.budget_currency, o.budget_note,
    COALESCE(
        (
            SELECT ep.url
            FROM application_endpoints ep
            WHERE ep.opportunity_id = o.id
              AND ep.is_active = 1
            ORDER BY ep.verified_at DESC, ep.id DESC
            LIMIT 1
        ),
        o.apply_url
    ) AS apply_url,
    o.output_status, o.fact_confidence, o.source_tier,
    p.display_name AS program_name,
    p.category,
    org.display_name AS org_name,
    fr.fit_score,
    fr.priority_score,
    fr.why_fit,
    fr.next_action
FROM opportunities o
JOIN programs p ON o.program_id = p.id
JOIN organizations org ON p.org_id = org.id
LEFT JOIN fit_recommendations fr
    ON fr.opportunity_id = o.id
    AND fr.company_profile_id = :company_profile_id
WHERE
    o.output_status = 'verified'
    AND o.fact_confidence >= :min_confidence
    AND o.source_tier <= 4
    AND EXISTS (
        SELECT 1
        FROM application_endpoints ep
        WHERE ep.opportunity_id = o.id
          AND ep.is_active = 1
    )
    AND o.status != 'closed'
    AND (o.days_left IS NULL OR o.days_left >= 0)
    AND (o.deadline_at IS NULL OR DATE(o.deadline_at) >= DATE('now', 'localtime'))
"""

CURATED_VIEW_CATEGORY_FILTER = """
    AND p.category = :category
"""

# Display bucket 기반 필터 (IN 절 사용)
# entity_store에서 동적으로 placeholders를 채운다
CURATED_VIEW_DISPLAY_BUCKET_FILTER_TEMPLATE = """
    AND p.category IN ({placeholders})
"""

CURATED_VIEW_ORDER = """
ORDER BY
    COALESCE(fr.priority_score, 0) DESC,
    o.fact_confidence DESC,
    COALESCE(o.days_left, 9999) ASC
LIMIT :limit
"""

# 카테고리별 기회 수
COUNT_BY_CATEGORY = """
SELECT COUNT(*) FROM opportunities o
JOIN programs p ON o.program_id = p.id
WHERE p.category = :category
"""

# 전체 기회 수
COUNT_ALL = """
SELECT COUNT(*) FROM opportunities
"""

# 특정 상태의 기회 수
COUNT_BY_STATUS = """
SELECT COUNT(*) FROM opportunities
WHERE status = :status
"""
