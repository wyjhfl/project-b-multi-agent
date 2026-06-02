from __future__ import annotations

from app.models.schemas import (
    AuditScopeDraft,
    OrganizationScopeDraft,
    PrincipalScopeDraft,
    ProjectScopeDraft,
    ResourceScopeDraft,
    RoleAssignmentDraft,
    TenantOwnershipModelDraft,
    TenantResourceAction,
    TenantScopeDraft,
    TenantScopeType,
)
from scripts.identity_tenant_boundary_inventory import build_identity_tenant_boundary_inventory


def _draft_model() -> TenantOwnershipModelDraft:
    organization = OrganizationScopeDraft(organization_id="org_demo", name="Demo Org")
    tenant = TenantScopeDraft(tenant_id="tenant_demo", organization_id="org_demo", name="Demo Tenant")
    project = ProjectScopeDraft(
        project_id="project_demo",
        tenant_id="tenant_demo",
        organization_id="org_demo",
        name="Demo Project",
    )
    principal = PrincipalScopeDraft(
        principal_id="usr_demo",
        username="operator",
        organization_id="org_demo",
        tenant_id="tenant_demo",
        project_id="project_demo",
    )
    role_assignment = RoleAssignmentDraft(
        assignment_id="ra_demo",
        principal_id="usr_demo",
        role="operator",
        scope_type=TenantScopeType.project,
        scope_id="project_demo",
    )
    resource_scope = ResourceScopeDraft(
        resource_id="task_demo",
        resource_type="task",
        organization_id="org_demo",
        tenant_id="tenant_demo",
        project_id="project_demo",
        owner_principal_id="usr_demo",
        allowed_actions=[TenantResourceAction.read, TenantResourceAction.write],
    )
    audit_scope = AuditScopeDraft(
        organization_id="org_demo",
        tenant_id="tenant_demo",
        project_id="project_demo",
        resource_id="task_demo",
        actor_principal_id="usr_demo",
        decision="allow",
    )
    return TenantOwnershipModelDraft(
        organization=organization,
        tenant=tenant,
        project=project,
        principal=principal,
        role_assignments=[role_assignment],
        resource_scope=resource_scope,
        audit_scope=audit_scope,
    )


def test_tenant_ownership_model_draft_captures_scope_relationships() -> None:
    model = _draft_model()

    assert model.organization.organization_id == "org_demo"
    assert model.tenant.organization_id == "org_demo"
    assert model.project is not None
    assert model.project.tenant_id == "tenant_demo"
    assert model.principal.tenant_id == "tenant_demo"
    assert model.role_assignments[0].scope_type == TenantScopeType.project
    assert model.resource_scope is not None
    assert TenantResourceAction.write in model.resource_scope.allowed_actions
    assert model.audit_scope is not None
    assert model.audit_scope.decision == "allow"


def test_tenant_ownership_model_draft_is_not_runtime_enforcement() -> None:
    model = _draft_model()

    assert model.draft_only is True
    assert model.tenant_enforcement_enabled is False
    assert "tenant_id" in model.jwt_future_claims
    assert "resource_scope" in model.server_store_fields


def test_tenant_inventory_reflects_draft_model_without_claiming_enforcement(tmp_path) -> None:
    summary = build_identity_tenant_boundary_inventory(output_dir=tmp_path / "out")

    import json
    from pathlib import Path

    payload = json.loads(Path(summary["json_path"]).read_text(encoding="utf-8"))
    gap_ids = {item["gap_id"] for item in payload["gaps"]}

    assert payload["resource_ownership"]["ownership_model_present"] is True
    assert payload["resource_ownership"]["runtime_enforcement_enabled"] is False
    assert "tenant:ownership_model_missing" not in gap_ids
    assert "tenant:runtime_enforcement_missing" in gap_ids
