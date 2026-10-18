from blinka.domain.pdf_boundaries import (
    BoundaryStatus,
    PdfBoundaryResult,
    PdfSecurityBoundaryResult,
    PdfSecurityStatus,
)


def test_pdf_security_contract_accepts_continue_result() -> None:
    boundary = PdfBoundaryResult(
        boundary_id="PDF-SEC-001",
        category="SECURITY",
        status=BoundaryStatus.PASS,
        reason_code="PDF_TEXT_EXTRACTABLE",
        message="Texto extraíble.",
        next_state="EXTRACTING",
    )
    result = PdfSecurityBoundaryResult(
        document_id="DOC-1",
        security_status=PdfSecurityStatus.ACCEPTED,
        next_state="EXTRACTING",
        boundaries=[boundary],
        content_sha256="a" * 64,
        page_count=2,
        extracted_text_bytes=120,
    )
    assert result.moves_money is False
    assert result.boundaries[0].status is BoundaryStatus.PASS


def test_pdf_security_contract_represents_block() -> None:
    boundary = PdfBoundaryResult(
        boundary_id="PDF-SEC-004",
        category="SECURITY",
        status=BoundaryStatus.BLOCK,
        reason_code="PDF_PAGE_LIMIT_EXCEEDED",
        message="Demasiadas páginas.",
        evidence={"page_count": 101, "max_pages": 100},
        next_state="FRENAR",
    )
    result = PdfSecurityBoundaryResult(
        document_id="DOC-2",
        security_status=PdfSecurityStatus.BLOCKED,
        next_state="FRENAR",
        boundaries=[boundary],
        content_sha256="b" * 64,
        page_count=101,
        extracted_text_bytes=0,
    )
    assert result.next_state == "FRENAR"
    assert result.boundaries[0].reason_code == "PDF_PAGE_LIMIT_EXCEEDED"
