"""The 33 source columns; original text stays editable without inferred values."""
FIELDS = dict([
('source_serial','FsnF'), ('booking_date','Booking Date'), ('shipper','SHIPPER'),
('tis_bill_no','TIS BILL NO.'), ('services','SERVICES'), ('empty_pickup','Empty Pickup'),
('pol','POL'), ('pod','POD'), ('final_destination','Final Destination'),
('current_status','CURRENT STATUS'), ('container_no','Container No.'),
('size_type','Size/Type'), ('booking_no','Booking No.'), ('shipping_line','SLine(FWD)'),
('planned_vessel','PLANNED VESSEL NAME'), ('etd','ETD'), ('eta','ETA'), ('bl_no','BL No.'),
('invoice_no','Invoice No.'), ('pickup_date','Pickup Date'), ('gate_in_date','Gate-In Date'),
('vgm_submitted','VGM Submitted (Y/N)'), ('si_submitted','SI Submitted'),
('bl_draft_status','BL Draft Status'), ('actual_vessel','Actual Vessel'),
('actual_date','Actual Date'), ('debit_note_received','Debit note received'),
('liner_payment_status','Liner Payment LFD and Status'), ('bl_type','BL Type'),
('bl_issued','BL issued (Y/N)'), ('tis_bill_sent','TIS BILL SENT'),
('remark','REMARK'), ('next_action','NEXT ACTION')])
DATE_FIELDS = {'booking_date','etd','eta','pickup_date','gate_in_date','actual_date'}

def review_flags(data):
    from datetime import date
    flags = []
    for name in DATE_FIELDS:
        value = data.get(name)
        if value:
            try:
                date.fromisoformat(value)
            except ValueError:
                flags.append(f'{FIELDS[name]}: confirm date and enter YYYY-MM-DD; original value preserved.')
    return sorted(flags)
