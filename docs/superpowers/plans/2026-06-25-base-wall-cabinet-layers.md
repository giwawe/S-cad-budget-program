# Base And Wall Cabinet Layers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `QUOTE_BASE_CABINET` and `QUOTE_WALL_CABINET` CAD layers so base cabinets and wall cabinets can be marked without relying on `TYPE` attributes.

**Architecture:** Keep the existing `QUOTE_CABINET` path for backward compatibility. Treat the two new layers as cabinet fixture markers with fixed `fixture_type` values, then reuse existing room assignment, cabinet detail, and quote aggregation logic.

**Tech Stack:** Python, pydantic models, ezdxf DXF adapter, pytest, openpyxl-backed quote tests.

---

### Task 1: Add Failing Model And DXF Tests

**Files:**
- Modify: `tests/test_models.py`
- Modify: `tests/test_dxf_adapter.py`

- [ ] **Step 1: Write the failing tests**

Add assertions that `LayerName` exposes `QUOTE_BASE_CABINET` and `QUOTE_WALL_CABINET`, and that DXF import maps those layers to `fixture_type="地柜"` and `fixture_type="吊柜"` while preserving both overlapping lines.

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; py -3.14 -m pytest tests\test_models.py::test_layer_name_includes_explicit_cabinet_type_layers tests\test_dxf_adapter.py::test_imports_base_and_wall_cabinet_layers_as_typed_cabinet_markers -q`

Expected: fail because the new enum values and import branches do not exist yet.

### Task 2: Implement Layer Import

**Files:**
- Modify: `src/cad_budget/models.py`
- Modify: `src/cad_budget/dxf_adapter.py`

- [ ] **Step 1: Add enum values**

Add `QUOTE_BASE_CABINET` and `QUOTE_WALL_CABINET` to `LayerName`.

- [ ] **Step 2: Add DXF import mapping**

For `LINE` and `LWPOLYLINE` on `QUOTE_BASE_CABINET`, create a `FixtureKind.CABINET` marker with `fixture_type="地柜"`. For `QUOTE_WALL_CABINET`, use `fixture_type="吊柜"`. Reuse the existing `_fixture_marker_from_points` helper and keep any parsed attributes.

- [ ] **Step 3: Run targeted tests**

Run the same command from Task 1. Expected: pass.

### Task 3: Document The Drawing Standard

**Files:**
- Modify: `README.md`
- Modify: `docs/cad-lightweight-drawing-standard-zh.md`

- [ ] **Step 1: Update layer lists**

Add `QUOTE_BASE_CABINET` and `QUOTE_WALL_CABINET` next to `QUOTE_CABINET`.

- [ ] **Step 2: Update designer guidance**

Explain that new drawings should prefer the explicit base/wall cabinet layers, while `QUOTE_CABINET + TYPE=地柜/吊柜` remains supported for compatibility.

### Task 4: Verify

**Files:**
- Test: `tests/test_models.py`
- Test: `tests/test_dxf_adapter.py`
- Test: full suite

- [ ] **Step 1: Run targeted tests**

Run: `$env:PYTHONPATH='src'; py -3.14 -m pytest tests\test_models.py tests\test_dxf_adapter.py tests\test_quantity.py tests\test_quote_excel.py -q`

- [ ] **Step 2: Run full suite**

Run: `$env:PYTHONPATH='src'; py -3.14 -m pytest -q`

- [ ] **Step 3: Commit**

Commit with message: `feat: add explicit cabinet type layers`.
