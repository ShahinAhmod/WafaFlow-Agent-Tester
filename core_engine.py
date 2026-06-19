# core_engine.py
# The Single Source of Truth (Full Accountant Mode v2)

def _line_total(item: dict) -> float:
    return item.get('total_price', item.get('total', 0))


def calculate_ap_match(invoice: dict, purchase_order: dict, receiving_report: dict = None) -> dict:
    inv_items = invoice.get('line_items', [])
    po_items = purchase_order.get('line_items', [])
    
    max_unit_variance = 0.0
    total_financial_impact = 0.0
    has_any_error = False
    
    max_lines = max(len(inv_items), len(po_items))
    
    for i in range(max_lines):
        inv_item = inv_items[i] if i < len(inv_items) else {}
        po_item = po_items[i] if i < len(po_items) else {}
        
        inv_price = inv_item.get('unit_price', 0)
        po_price = po_item.get('unit_price', 0)
        inv_qty = inv_item.get('quantity', 0)
        po_qty = po_item.get('quantity', 0)
        inv_total = _line_total(inv_item)
        po_total = _line_total(po_item)
        
        # Check Unit Price
        unit_var = abs(inv_price - po_price)
        if unit_var > max_unit_variance:
            max_unit_variance = unit_var
            
        # Check Quantity
        if inv_qty != po_qty:
            has_any_error = True
            
        # Check Total Price for the line
        if abs(inv_total - po_total) > 0.01:
            has_any_error = True
            
        # Calculate financial impact of the unit price variance
        total_financial_impact += (unit_var * inv_qty)

    # Check overall document totals
    doc_total_variance = abs(invoice.get('total_amount', 0) - purchase_order.get('total_amount', 0))
    if doc_total_variance > 0.01:
        has_any_error = True

    # 3-Way Match: validate receiving report quantities if provided
    if receiving_report:
        rr_items = receiving_report.get('line_items', [])
        for i in range(max(len(inv_items), len(rr_items))):
            inv_item = inv_items[i] if i < len(inv_items) else {}
            rr_item = rr_items[i] if i < len(rr_items) else {}
            inv_qty = inv_item.get('quantity', 0)
            rr_qty = rr_item.get('quantity_received', rr_item.get('quantity', 0))
            if inv_qty != rr_qty:
                has_any_error = True

    # Business Logic: Reject if unit price variance > 0.05 OR if any other field mismatches
    if max_unit_variance > 0.05 or has_any_error:
        status = "REJECTED"
    else:
        status = "APPROVED"
        
    return {
        "status": status,
        "unit_price_variance": round(max_unit_variance, 2),
        "total_financial_impact": round(total_financial_impact, 2),
        "total_amount_variance": round(doc_total_variance, 2) # <--- NEW METRIC
    }