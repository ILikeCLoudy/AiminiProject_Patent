"""Korean narrative text formatting for patent assessment reports."""
from __future__ import annotations

from typing import Any, Dict, List


def format_scope_method_kr(data: Dict[str, Any]) -> List[str]:
    """Convert scope & method section to Korean narrative paragraphs."""
    narratives: List[str] = []

    scope = data.get("scope", {})
    method = data.get("method", {})

    # Scope narrative
    if scope:
        keywords = scope.get("keywords", "")
        cpc = scope.get("cpc", "")
        period = scope.get("period", "")
        target = scope.get("target_market", "")

        scope_text = (
            f"본 평가는 {keywords or '지정된 기술'}과 관련된 특허를 대상으로 하며, "
            f"CPC 코드 {cpc or '다양한 카테고리'}로 분류됩니다. "
            f"분석 기간은 {period or '미지정 기간'}이며, "
            f"{target or '일반 시장'} 애플리케이션에 중점을 둡니다."
        )
        narratives.append(scope_text)

    # Method narrative
    if method:
        norm = method.get("normalisation", "")
        weights = method.get("weights", "")
        rules = method.get("label_rule", "")

        method_text = (
            f"우리의 평가 방법론은 {norm or '표준 정규화'}를 적용하여 지표 간 공정한 비교를 보장합니다. "
            f"개별 지표는 {weights or '사전 정의된 가중치'}를 사용하여 결합되어 종합 점수를 생성합니다. "
            f"최종 권장사항은 전체 성능과 리스크 요인을 기반으로 {rules or '확립된 의사결정 규칙'}을 따릅니다."
        )
        narratives.append(method_text)

    return narratives


def format_dataset_kr(data: Dict[str, Any]) -> List[str]:
    """Convert dataset overview to Korean narrative."""
    narratives: List[str] = []

    doc_count = data.get("documents", 0)
    family_size = data.get("family_size", 0)
    quality = data.get("quality", {})

    # Document count narrative
    dataset_text = (
        f"본 평가에서 {doc_count}개의 특허 문서를 분석했습니다. "
        f"특허 패밀리는 여러 관할권에 걸쳐 {family_size}개의 멤버로 구성됩니다."
    )
    narratives.append(dataset_text)

    # Quality issues
    if quality:
        missing = quality.get("missing_metrics", [])
        if missing:
            quality_text = (
                f"데이터 품질 참고사항: {len(missing)}개 지표({', '.join(missing[:3])}"
                f"{', ...' if len(missing) > 3 else ''})를 공개 출처에서 조회할 수 없었습니다. "
                f"이는 분석의 포괄성에 영향을 미칠 수 있습니다."
            )
            narratives.append(quality_text)

    return narratives


def format_core_metrics_kr(data: Dict[str, Any]) -> List[str]:
    """Convert core metrics to Korean narrative explanations."""
    narratives: List[str] = []

    # Citations
    citations = data.get("citations_total", 0)
    if citations == 0:
        cit_text = (
            "이 특허는 아직 다른 특허에 인용되지 않았습니다. "
            "이는 최근 출원이거나, 해당 분야에서 기술적 영향력이 제한적임을 시사할 수 있습니다."
        )
    elif citations < 5:
        cit_text = (
            f"이 특허는 다른 특허에 {citations}회 인용되었으며, "
            "기술 커뮤니티에서 점진적인 인정을 받고 있음을 나타냅니다."
        )
    else:
        cit_text = (
            f"이 특허는 {citations}회의 후방 인용을 받았으며, "
            "이는 상당한 기술적 영향력과 후속 혁신과의 관련성을 입증합니다."
        )
    narratives.append(cit_text)

    # Family
    family = data.get("family", 1)
    if family == 1:
        fam_text = (
            "이는 국제 패밀리 멤버가 없는 독립형 특허입니다. "
            "출원인은 다른 관할권에 동등한 출원을 하지 않았습니다."
        )
    else:
        fam_text = (
            f"이 특허는 여러 관할권에 걸쳐 {family}개의 멤버로 구성된 패밀리에 속하며, "
            "출원인의 국제 보호에 대한 전략적 관심을 나타냅니다."
        )
    narratives.append(fam_text)

    # Legal status
    legal = data.get("legal_status", "")
    if legal and legal.lower() == "active":
        legal_text = (
            "특허는 현재 유효하며 시행 중이고, 유지비가 최신 상태로 납부되었습니다. "
            "이는 특허 보유자에게 지속적인 상업적 가치와 전략적 중요성이 있음을 나타냅니다."
        )
    elif legal and legal.lower() in ("expired", "abandoned"):
        legal_text = (
            f"특허는 {legal}되어 더 이상 독점권을 제공하지 않습니다. "
            "이는 우리 구현에 대한 자유실시(FTO) 기회를 제공할 수 있습니다."
        )
    else:
        legal_text = f"법적 상태: {legal or '알 수 없음 - 추가 조사 필요'}."
    narratives.append(legal_text)

    # TRL score
    trl = data.get("trl_score")
    if trl is not None:
        if trl >= 8:
            trl_text = (
                f"기술성숙도(TRL) 분석 결과 이 특허는 {trl:.1f}점을 받았으며, "
                "이는 기술이 운영 환경에 배포되었음을 나타냅니다. "
                "이는 높은 성숙도와 입증된 실제 실행 가능성을 시사합니다."
            )
        elif trl >= 6:
            trl_text = (
                f"기술성숙도(TRL) {trl:.1f}점은 기술이 파일럿 테스트를 통해 "
                "관련 환경에서 시연되었음을 나타냅니다. "
                "전면 배포 전에 추가 검증이 필요할 수 있습니다."
            )
        else:
            trl_text = (
                f"기술성숙도(TRL) {trl:.1f}점은 초기 단계 개발을 시사합니다. "
                "상업적 준비를 위해서는 상당한 추가 작업이 필요합니다."
            )
        narratives.append(trl_text)

    # Claim score
    claim = data.get("claim_score")
    if claim is not None:
        if claim >= 80:
            claim_text = (
                f"청구항 범위 분석 결과 {claim:.1f}점을 받았으며, "
                "이는 균형 잡힌 범위를 가진 잘 구조화된 청구항을 나타냅니다. "
                "특허는 지나치게 광범위하거나 좁지 않으면서 강력한 보호를 제공합니다."
            )
        elif claim >= 60:
            claim_text = (
                f"청구항 범위 점수 {claim:.1f}점은 중간 수준의 특허 적용 범위를 시사합니다. "
                "청구항은 보호 범위를 최적화하기 위해 개선이 필요할 수 있습니다."
            )
        else:
            claim_text = (
                f"청구항 범위 점수 {claim:.1f}점은 특허 범위의 잠재적 제한을 나타냅니다. "
                "청구항이 너무 좁거나 장황하여 집행 옵션을 제한할 수 있습니다."
            )
        narratives.append(claim_text)

    return narratives


def format_edge_fitness_kr(data: Dict[str, Any]) -> List[str]:
    """Convert edge fitness metrics to Korean narrative."""
    narratives: List[str] = []

    # Handle nested metrics structure
    if isinstance(data, dict) and not data:
        return [
            "이 특허에 대한 엣지 디바이스 성능 지표를 사용할 수 없었습니다. "
            "공개 출처의 실험 데이터 또는 벤치마크 부족으로 평가를 수행할 수 없었습니다."
        ]

    metrics = data if not isinstance(data.get("latency_ms"), dict) else {
        k: v.get("value") if isinstance(v, dict) else v
        for k, v in data.items()
    }

    if all(v is None for v in metrics.values()):
        return [
            "이 특허에 대한 엣지 디바이스 성능 지표를 사용할 수 없었습니다. "
            "공개 출처의 실험 데이터 또는 벤치마크 부족으로 평가를 수행할 수 없었습니다."
        ]

    # Thresholds
    latency_threshold = 50
    power_threshold = 600
    memory_threshold = 256

    # Latency
    latency = metrics.get("latency_ms")
    if latency is not None:
        if latency <= latency_threshold:
            lat_text = (
                f"추론 지연시간은 {latency}ms로 측정되어, 엣지 배포 임계값 "
                f"{latency_threshold}ms를 충족합니다. 이는 실시간 처리 능력을 나타냅니다."
            )
        else:
            lat_text = (
                f"추론 지연시간 {latency}ms는 목표 임계값({latency_threshold}ms)을 초과합니다. "
                "지연시간에 민감한 엣지 애플리케이션을 위해 최적화가 필요할 수 있습니다."
            )
        narratives.append(lat_text)

    # Power
    power = metrics.get("power_mw")
    if power is not None:
        if power <= power_threshold:
            pow_text = (
                f"전력 소비는 {power}mW로, 엣지 디바이스 예산 {power_threshold}mW를 충족합니다. "
                "이는 배터리 구동 배포 시나리오를 가능하게 합니다."
            )
        else:
            pow_text = (
                f"전력 소비 {power}mW는 예산({power_threshold}mW)을 초과합니다. "
                "이는 전력 제약 디바이스에 대한 적용성을 제한할 수 있습니다."
            )
        narratives.append(pow_text)

    # Memory
    memory = metrics.get("memory_mb")
    if memory is not None:
        if memory <= memory_threshold:
            mem_text = (
                f"메모리 풋프린트는 {memory}MB로, {memory_threshold}MB 엣지 디바이스 제약 내에 있습니다. "
                "모델은 리소스가 제한된 하드웨어에서 실행될 수 있습니다."
            )
        else:
            mem_text = (
                f"메모리 요구사항 {memory}MB는 {memory_threshold}MB 한계를 초과합니다. "
                "모델 압축 기술이 필요할 수 있습니다."
            )
        narratives.append(mem_text)

    # Accuracy delta
    acc_delta = metrics.get("accuracy_delta")
    if acc_delta is not None:
        if acc_delta >= 0:
            acc_text = (
                f"기준선 대비 정확도는 {acc_delta:+.1f}% 변화를 보여, "
                "엣지 최적화로 인한 성능 저하가 없음을 나타냅니다."
            )
        elif acc_delta >= -2:
            acc_text = (
                f"기준선 대비 정확도는 {acc_delta:+.1f}% 변화를 보입니다. "
                "이 경미한 성능 저하는 엣지 배포에 허용 가능합니다."
            )
        else:
            acc_text = (
                f"정확도 저하 {acc_delta:+.1f}%는 우려를 야기합니다. "
                "정확도와 효율성의 균형을 맞추기 위해 추가 최적화가 필요할 수 있습니다."
            )
        narratives.append(acc_text)

    return narratives


def format_competitive_kr(data: Dict[str, Any]) -> List[str]:
    """Convert competitive & standards section to Korean narrative."""
    narratives: List[str] = []

    sep = data.get("sep", "")

    if sep == "declared":
        sep_text = (
            "이 특허는 표준필수특허(SEP)로 선언되었으며, "
            "이는 특정 산업 표준을 구현하는 데 필수적임을 의미합니다. "
            "이는 상당한 전략적 가치를 제공하지만 FRAND 라이선싱 의무가 따를 수 있습니다."
        )
    elif sep == "not_declared":
        sep_text = (
            "이 특허는 표준필수로 선언되지 않았습니다. "
            "이는 더 큰 라이선싱 유연성을 제공하지만, 표준 기반 가치가 제한적일 수 있습니다."
        )
    else:
        sep_text = (
            "표준필수특허(SEP) 상태를 확인할 수 없었습니다. "
            "표준화 기구(ETSI, IEEE 등)와의 추가 조사가 권장됩니다."
        )
    narratives.append(sep_text)

    return narratives


def format_risk_profile_kr(data: Dict[str, Any]) -> List[str]:
    """Convert risk profile to Korean narrative."""
    narratives: List[str] = []

    gaps = data.get("data_gaps", [])

    if gaps:
        gap_text = (
            f"리스크 평가에서 {len(gaps)}개의 누락된 데이터 포인트를 식별했습니다: {', '.join(gaps[:3])}"
            f"{', ...' if len(gaps) > 3 else ''}. "
            "이러한 격차는 분석의 특정 측면에 대한 신뢰도를 낮춥니다. "
            "최종 결정을 내리기 전에 추가 출처에서 수동 검증을 강력히 권장합니다."
        )
        narratives.append(gap_text)
    else:
        gap_text = "모든 주요 지표가 성공적으로 조회되어 평가에 대한 높은 신뢰도를 제공합니다."
        narratives.append(gap_text)

    return narratives


def format_ranking_kr(data: Dict[str, Any]) -> List[str]:
    """Convert ranking & labelling to Korean narrative."""
    narratives: List[str] = []

    total = data.get("total_score")
    label = data.get("label", "")

    if total is not None:
        rank_text = (
            f"이 특허의 전체 가중 점수는 100점 만점에 {total:.2f}점으로, "
            f"권장 레이블은 '{label}'입니다. "
        )

        if label == "A":
            rank_text += (
                "이 'Adopt(채택)' 레이블은 특허가 유리한 기술적, 시장적, 법적 특성을 가진 "
                "강력한 기회를 나타냄을 의미합니다. 즉각적인 조치가 권장됩니다."
            )
        elif label == "P":
            rank_text += (
                "이 'Prototype(시제품)' 레이블은 특허가 가능성을 보이지만 추가 검증이 필요함을 시사합니다. "
                "전면 투입 전에 파일럿 구현 또는 심층 기술 실사를 고려하세요."
            )
        elif label == "M":
            rank_text += (
                "이 'Monitor(모니터링)' 레이블은 현재 한계적 가치를 나타냅니다. "
                "개발 상황을 계속 추적하되 조건이 개선될 때까지 투자를 연기하세요."
            )
        else:
            rank_text += (
                "특허는 현재 우리의 전략적 기준을 충족하지 않습니다. "
                "상황이 변경되면 향후 재고를 위해 보관하세요."
            )

        narratives.append(rank_text)

    return narratives


def format_conclusion_kr(data: Dict[str, Any]) -> List[str]:
    """Convert conclusion section to Korean narrative."""
    if isinstance(data, dict):
        return [f"{k}: {v}" for k, v in data.items() if v]
    elif isinstance(data, list):
        return data
    return [str(data)] if data else []


def format_candidate_cards_kr(cards: List[Dict[str, Any]]) -> List[str]:
    """Convert decision cards to Korean narrative."""
    narratives: List[str] = []

    for card in cards:
        title = card.get("title", "알 수 없음")
        decision = card.get("decision", "")
        signals = card.get("signals", [])
        risks = card.get("risks", [])

        card_text = (
            f"특허 {title}: 권장 조치는 '{decision}'입니다. "
            f"주요 긍정적 신호: {', '.join(signals) if signals else '식별되지 않음'}. "
        )

        if risks:
            risk_items = [r.get("item", "") for r in risks if isinstance(r, dict)]
            card_text += f"고려해야 할 리스크 요인: {', '.join(risk_items)}."

        narratives.append(card_text)

    return narratives


def format_main_body_section_kr(section_name: str, data: Any) -> List[str]:
    """Main dispatcher for formatting different sections in Korean."""
    if not data:
        return [f"{section_name}에 대한 데이터를 사용할 수 없습니다."]

    formatters = {
        "scope_method": format_scope_method_kr,
        "dataset": format_dataset_kr,
        "core_metrics": format_core_metrics_kr,
        "edge_fitness": format_edge_fitness_kr,
        "competitive": format_competitive_kr,
        "risk_profile": format_risk_profile_kr,
        "ranking": format_ranking_kr,
        "conclusion": format_conclusion_kr,
        "candidate_cards": format_candidate_cards_kr,
    }

    formatter = formatters.get(section_name)
    if formatter:
        if section_name == "candidate_cards" and isinstance(data, list):
            return formatter(data)
        elif isinstance(data, dict):
            return formatter(data)

    # Fallback: return as-is
    if isinstance(data, dict):
        return [f"{k}: {v}" for k, v in data.items() if v not in (None, "", [])]
    elif isinstance(data, list):
        return [str(item) for item in data]
    return [str(data)]


__all__ = ["format_main_body_section_kr"]
