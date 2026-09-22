from app.filenames import sanitize_filename_stem


def test_keeps_normal_filename():
    assert sanitize_filename_stem("invoice") == "invoice"
    assert sanitize_filename_stem("September Invoice") == "September Invoice"


def test_strips_surrounding_whitespace():
    assert sanitize_filename_stem("  invoice  ") == "invoice"


def test_removes_pdf_extension():
    assert sanitize_filename_stem("invoice.pdf") == "invoice"


def test_removes_forward_slash_path():
    assert sanitize_filename_stem("../../secret") == "secret"


def test_removes_windows_path():
    assert sanitize_filename_stem("..\\..\\secret") == "secret"


def test_removes_unsafe_characters():
    assert sanitize_filename_stem("Invoice: Q3 <Draft>?") == "Invoice Q3 Draft"


def test_blank_filename_falls_back_to_invoice():
    assert sanitize_filename_stem("") == "invoice"
    assert sanitize_filename_stem("   ") == "invoice"


def test_dot_dot_falls_back_to_invoice():
    assert sanitize_filename_stem("..") == "invoice"
    assert sanitize_filename_stem("facturé septembre") == "facturé septembre"
    assert sanitize_filename_stem("CON") == "invoice"
    assert sanitize_filename_stem("nul") == "invoice"
    assert sanitize_filename_stem("../../") == "invoice"
    assert sanitize_filename_stem("customer/invoice") == "invoice"
    assert sanitize_filename_stem("customer\\invoice") == "invoice"
