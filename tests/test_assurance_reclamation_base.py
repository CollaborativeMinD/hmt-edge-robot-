"""Shared test_assurance_reclamation primitives and declarations."""






def setup_artifact(cell, **refs):
    catalog = cell.assurance.catalog
    record = catalog.put("model", b"weights")
    if refs:
        record = record.model_copy(update=refs)
        catalog.update(record)
    return record

def plan(cell):
    return cell.assurance.agc.plan(cell.assurance.catalog.census())

def grant(cell, current, action, session):
    return cell.assurance.issue_grant(current, action, "model", session, "operator")
