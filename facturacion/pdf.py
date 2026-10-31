from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _moneda(valor):
    return f"L {valor:,.2f}"


def generar_recibo_pdf(pago):
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=pago.numero_recibo,
    )
    styles = getSampleStyleSheet()
    brand = colors.HexColor("#153B63")
    muted = colors.HexColor("#66788A")
    styles.add(ParagraphStyle(name="Brand", parent=styles["Title"], textColor=brand, fontSize=20, leading=24, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="MutedCenter", parent=styles["Normal"], textColor=muted, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="Right", parent=styles["Normal"], alignment=TA_RIGHT))
    story = [
        Paragraph(pago.casa.colonia.nombre, styles["Brand"]),
        Paragraph("Recibo de vigilancia", styles["MutedCenter"]),
        Spacer(1, 8 * mm),
    ]
    if pago.anulado:
        alert = Table([["RECIBO ANULADO"]], colWidths=[166 * mm])
        alert.setStyle(TableStyle([
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#B42318")),
            ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#B42318")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("PADDING", (0, 0), (-1, -1), 8),
        ]))
        story.extend([alert, Spacer(1, 5 * mm)])
    cabecera = Table([
        [Paragraph("<font color='#66788A' size='8'>RECIBO</font><br/><b>%s</b>" % pago.numero_recibo, styles["Normal"]),
         Paragraph("<font color='#66788A' size='8'>FECHA</font><br/><b>%s</b>" % pago.fecha_pago.strftime("%d/%m/%Y"), styles["Right"])],
        [Paragraph("<font color='#66788A' size='8'>CASA</font><br/><b>#%s</b>" % pago.casa.codigo, styles["Normal"]),
         Paragraph("<font color='#66788A' size='8'>RESPONSABLE</font><br/><b>%s</b>" % pago.responsable.nombre_completo, styles["Right"])],
    ], colWidths=[83 * mm, 83 * mm], rowHeights=[16 * mm, 16 * mm])
    cabecera.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), .5, colors.HexColor("#DFE6EE"))]))
    story.extend([cabecera, Spacer(1, 5 * mm)])
    filas = [["Concepto", "Monto"]]
    for aplicacion in pago.aplicaciones.select_related("cuota_mensual"):
        filas.append([f"Vigilancia {aplicacion.cuota_mensual.periodo}", _moneda(aplicacion.monto_aplicado)])
    filas.append(["Total recibido", _moneda(pago.monto_total)])
    tabla = Table(filas, colWidths=[120 * mm, 46 * mm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF4F8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), brand), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("GRID", (0, 0), (-1, -2), .35, colors.HexColor("#DFE6EE")),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, brand), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([tabla, Spacer(1, 7 * mm)])
    detalles = Table([
        ["Forma de pago", pago.get_metodo_pago_display(), "Referencia", pago.referencia or "No aplica"],
        ["Recibido por", pago.usuario_que_registra.nombre_completo, "", ""],
    ], colWidths=[28 * mm, 55 * mm, 28 * mm, 55 * mm])
    detalles.setStyle(TableStyle([
        ("TEXTCOLOR", (0, 0), (0, -1), muted), ("TEXTCOLOR", (2, 0), (2, -1), muted),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.extend([detalles, Spacer(1, 12 * mm), Paragraph(f"Documento generado por Pase Seguro<br/>{pago.token_publico}", styles["MutedCenter"])])
    doc.build(story)
    return output.getvalue()
