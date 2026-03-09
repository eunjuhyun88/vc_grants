"""
Funding Intelligence Agent — SQL 쿼리 상수.

entity_store.py와 interface/handlers에서 사용.
"""

# Curated View: Eligibility Filter 적용된 기회 목록
CURATED_VIEW_SQL = """
SELECT
    o.id, o.status, o.deadline_at, o.days_left,
    o.budget_amount, o.budget_currency, o.budget_note,
    o.apply_url, o.output_status, o.fact_confidence, o.source_tier,
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
    AND o.source_tier <= 2
    AND o.apply_url IS NOT NULL
    AND o.status != 'closed'
"""

CURATED_VIEW_CATEGORY_FILTER = """
    AND p.category = :category
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
