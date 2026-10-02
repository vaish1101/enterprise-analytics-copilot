"""Serialize governed results for the approved UI; never calculate new values."""
from src.orchestration.models import WorkflowStatus
from .schemas import (AnalyticsChange, AnalyticsFact, AnalyticsResponse,
                      FactSourceResponse, RankedComponentResponse, ReconciliationResponse)

def fact(item, catalog):
    role, order = catalog.bridge_position(item.fact_id)
    return AnalyticsFact(
        fact_id=item.fact_id, company_id=item.company.value, metric_id=item.metric_id.value,
        label=item.reported_name, business_scope=item.business_scope, period=item.period.value,
        period_grain=item.period_grain.value, value=format(item.value, 'f'), unit=item.unit.value,
        provenance=item.provenance_type.value, bridge_role=role, component_order=order,
    )

def governed_numbers(result, evidence, claims, catalog):
    if result.status is not WorkflowStatus.COMPLETED:
        return None, []
    analytics = None
    if evidence is not None and evidence.analytics is not None and evidence.question_id == result.question_id:
        data = evidence.analytics
        kinds = {'ABSOLUTE_CHANGE': 'absolute', 'PERCENT_CHANGE': 'percent', 'PERCENTAGE_POINT_CHANGE': 'percentage_point'}
        units = {'absolute': data.primary_result.unit.value, 'percent': 'percent', 'percentage_point': 'percentage_point'}
        changes = [AnalyticsChange(kind=kinds[run.output_field.value], value=format(run.result_value, 'f'),
                   unit=units[kinds[run.output_field.value]], calculation_run_id=run.run_id)
                   for run in data.calculation_runs if run.output_field.value in kinds and run.result_value is not None]
        analytics = AnalyticsResponse(
            operation=data.operation.value, primary=fact(data.primary_result, catalog),
            comparison=fact(data.comparison_result, catalog) if data.comparison_result else None,
            changes=changes, components=[fact(item, catalog) for item in data.decomposition_components],
            supporting=[fact(item, catalog) for item in data.supporting_results],
            ranked=[RankedComponentResponse(rank=item.rank, fact_id=item.fact_id, metric_id=item.metric_id.value,
                    label=item.component_label, value=format(item.value, 'f'), unit=item.unit.value,
                    provenance=item.provenance_type.value) for item in data.ranked_components],
            reconciliations=[ReconciliationResponse(rule_id=item.rule_id.value, expected_value=format(item.expected_value, 'f'),
                calculated_value=format(item.calculated_value, 'f'), absolute_difference=format(item.absolute_difference, 'f'),
                tolerance=format(item.tolerance, 'f'), passed=item.passed, source_fact_ids=list(item.source_fact_ids),
                calculation_run_id=item.calculation_run_id) for item in data.reconciliation_results],
            calculation_run_ids=list(data.calculation_run_ids), warnings=[item.value for item in data.warnings],
            limitations=[item.value for item in data.limitations],
        )
        # A partial release must not serialize unverified numerical fields.
        released_facts = {fid for claim in claims for fid in claim.fact_ids}
        released_runs = {rid for claim in claims for rid in claim.calculation_run_ids}
        referenced = {analytics.primary.fact_id, *(item.fact_id for item in analytics.components),
                      *(item.fact_id for item in analytics.supporting)}
        if analytics.comparison:
            referenced.add(analytics.comparison.fact_id)
        if not referenced <= released_facts or not set(analytics.calculation_run_ids) <= released_runs:
            analytics = None
    sources = []
    for fid in dict.fromkeys(fid for claim in claims for fid in claim.fact_ids):
        source = catalog.fact_source(fid)
        if source is not None:
            sources.append(FactSourceResponse(**source))
    return analytics, sources
