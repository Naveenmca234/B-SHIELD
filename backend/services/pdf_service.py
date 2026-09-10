"""
pdf_service.py
--------------
Generates tamper-evident, professional Incident Dossier PDFs for B-SHIELD (IBVAP)
using ReportLab.
"""
import io
from datetime import datetime, timezone
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch


class IncidentPDFGenerator:
    """Generates official, print-ready B-SHIELD Incident Dossiers in PDF format."""

    @staticmethod
    def generate_incident_report(incident: Dict[str, Any], requested_by: str, role: str) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        # Custom styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0f172a"),
            alignment=1,  # Centered
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748b"),
            alignment=1,
        )
        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=8,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
        body_bold = ParagraphStyle(
            "BodyBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0f172a"),
        )
        mono_style = ParagraphStyle(
            "Mono",
            parent=styles["Normal"],
            fontName="Courier",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0f172a"),
        )
        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#94a3b8"),
            alignment=1,
        )

        story = []

        # 1. Header & Official Banner
        story.append(Paragraph("B-SHIELD (IBVAP) — INCIDENT DOSSIER", title_style))
        story.append(Paragraph("INTELLIGENT BORDER VIDEO ANALYTICS PLATFORM • OFFICIAL LAW ENFORCEMENT RECORD", subtitle_style))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0284c7"), spaceAfter=10))

        # 2. Key Metadata Grid
        incident_id = incident.get("incidentId", "N/A")
        camera_id = incident.get("cameraId", "N/A")
        event_type = incident.get("eventType", "N/A")
        status_val = incident.get("status", "NEW")
        severity = incident.get("severity", "MEDIUM")
        risk_score = incident.get("riskScore", incident.get("risk_score", 0))
        created_at = incident.get("createdAt", incident.get("timestamp", datetime.now(timezone.utc).isoformat()))

        # Severity color coding
        sev_color = colors.HexColor("#dc2626") if severity in ("CRITICAL", "HIGH") else colors.HexColor("#d97706")

        meta_data = [
            [
                Paragraph("<b>Incident ID:</b>", body_style),
                Paragraph(f"<b>{incident_id}</b>", body_bold),
                Paragraph("<b>Status:</b>", body_style),
                Paragraph(f"<b>{status_val}</b>", body_bold),
            ],
            [
                Paragraph("<b>Camera ID:</b>", body_style),
                Paragraph(camera_id, body_style),
                Paragraph("<b>Severity:</b>", body_style),
                Paragraph(f"<font color='{sev_color.hexval()}'><b>{severity}</b></font>", body_bold),
            ],
            [
                Paragraph("<b>Event Type:</b>", body_style),
                Paragraph(event_type, body_style),
                Paragraph("<b>Assessed Risk:</b>", body_style),
                Paragraph(f"<b>{risk_score} / 100</b>", body_bold),
            ],
            [
                Paragraph("<b>Detection Time:</b>", body_style),
                Paragraph(str(created_at), body_style),
                Paragraph("<b>Report Generated:</b>", body_style),
                Paragraph(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), body_style),
            ],
            [
                Paragraph("<b>Investigator / Operator:</b>", body_style),
                Paragraph(f"{requested_by} ({role})", body_style),
                Paragraph("<b>Classification:</b>", body_style),
                Paragraph("CONFIDENTIAL // BORDER SECURITY", body_bold),
            ],
        ]

        meta_table = Table(meta_data, colWidths=[1.4 * inch, 2.2 * inch, 1.4 * inch, 2.2 * inch])
        meta_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(meta_table)
        story.append(Spacer(1, 12))

        # 3. Multi-Cue Risk Breakdown & Description
        story.append(Paragraph("1. Explainable Threat Assessment & Cues", section_heading))
        risk_breakdown = incident.get("riskBreakdown", incident.get("risk_breakdown", {}))
        cues_text = []
        if isinstance(risk_breakdown, dict) and risk_breakdown:
            for k, v in risk_breakdown.items():
                cues_text.append(f"• <b>{k.replace('_', ' ').title()}:</b> {v}")
        else:
            cues_text.append("• Standard multi-cue risk scoring evaluated at detection time.")

        description = incident.get("description", f"Alert triggered at perimeter sector monitored by camera {camera_id}.")
        cues_paragraph = Paragraph("<br/>".join(cues_text) + f"<br/><br/><b>Incident Summary:</b> {description}", body_style)
        story.append(cues_paragraph)
        story.append(Spacer(1, 10))

        # 4. Tamper-Evident Evidence & Cryptographic Hashes
        story.append(Paragraph("2. Tamper-Evident Digital Evidence Chain", section_heading))
        evidence_list = incident.get("evidence", [])
        if evidence_list:
            ev_table_data = [
                [
                    Paragraph("<b>Evidence ID</b>", body_bold),
                    Paragraph("<b>Type</b>", body_bold),
                    Paragraph("<b>SHA-256 Checksum</b>", body_bold),
                    Paragraph("<b>Timestamp</b>", body_bold),
                ]
            ]
            for ev in evidence_list:
                ev_id = ev.get("evidenceId", "N/A")
                ev_type = ev.get("type", "SNAPSHOT")
                ev_hash = ev.get("sha256", "N/A")
                ev_time = ev.get("timestamp", "N/A")
                ev_table_data.append([
                    Paragraph(ev_id, body_style),
                    Paragraph(ev_type, body_style),
                    Paragraph(ev_hash[:20] + "..." if len(ev_hash) > 24 else ev_hash, mono_style),
                    Paragraph(str(ev_time)[:19] if str(ev_time) else "N/A", body_style),
                ])
            ev_table = Table(ev_table_data, colWidths=[1.6 * inch, 1.0 * inch, 3.0 * inch, 1.6 * inch])
            ev_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ])
            )
            story.append(ev_table)
        else:
            story.append(Paragraph("<i>No digital media artifacts attached to this incident.</i>", body_style))
        story.append(Spacer(1, 10))

        # 5. Lifecycle History / Audit Trail
        story.append(Paragraph("3. Incident Response & Lifecycle Audit Trail", section_heading))
        history_list = incident.get("history", [])
        if history_list:
            hist_data = [
                [
                    Paragraph("<b>State Change</b>", body_bold),
                    Paragraph("<b>Operator</b>", body_bold),
                    Paragraph("<b>Role</b>", body_bold),
                    Paragraph("<b>Timestamp</b>", body_bold),
                    Paragraph("<b>Reason / Notes</b>", body_bold),
                ]
            ]
            for h in history_list:
                from_s = h.get("fromStatus", "START")
                to_s = h.get("toStatus", h.get("status", "NEW"))
                u = h.get("changedBy", h.get("username", "System"))
                r = h.get("role", "operator")
                t = h.get("timestamp", "N/A")
                reason = h.get("reason", "—")
                hist_data.append([
                    Paragraph(f"{from_s} → {to_s}", body_style),
                    Paragraph(u, body_style),
                    Paragraph(r, body_style),
                    Paragraph(str(t)[:19] if str(t) else "N/A", body_style),
                    Paragraph(reason, body_style),
                ])
            hist_table = Table(hist_data, colWidths=[1.8 * inch, 1.2 * inch, 1.0 * inch, 1.5 * inch, 1.7 * inch])
            hist_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ])
            )
            story.append(hist_table)
        else:
            story.append(Paragraph("<i>No state transitions recorded yet. Current state: " + status_val + "</i>", body_style))
        story.append(Spacer(1, 10))

        # 6. Operator Feedback / Ground Truth
        story.append(Paragraph("4. Ground Truth & Operator Feedback", section_heading))
        feedback = incident.get("feedback")
        if feedback and isinstance(feedback, dict):
            f_class = str(feedback.get("classification") or "N/A")
            f_reason = str(feedback.get("reason") or "—")
            f_op = str(feedback.get("operator") or "N/A")
            f_notes = str(feedback.get("notes") or "—")
            f_time = str(feedback.get("timestamp") or "N/A")

            f_data = [
                [Paragraph("<b>Classification:</b>", body_style), Paragraph(f"<b>{f_class}</b>", body_bold)],
                [Paragraph("<b>Reason:</b>", body_style), Paragraph(f_reason, body_style)],
                [Paragraph("<b>Recorded By:</b>", body_style), Paragraph(f"{f_op} at {f_time[:19]}", body_style)],
                [Paragraph("<b>Investigation Notes:</b>", body_style), Paragraph(f_notes, body_style)],
            ]
            f_table = Table(f_data, colWidths=[1.8 * inch, 5.4 * inch])
            f_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ])
            )
            story.append(f_table)
        else:
            story.append(Paragraph("<i>Pending operator post-incident validation.</i>", body_style))
        story.append(Spacer(1, 16))

        # 7. Signature & Certification Block
        cert_data = [
            [
                Paragraph("<b>Investigating Security Officer:</b>", body_style),
                Paragraph("<b>Command Duty Officer / Authorization:</b>", body_style),
            ],
            [
                Paragraph("<br/><br/>________________________________________<br/>Signature & ID Number", body_style),
                Paragraph("<br/><br/>________________________________________<br/>Signature & Official Stamp", body_style),
            ],
        ]
        cert_table = Table(cert_data, colWidths=[3.6 * inch, 3.6 * inch])
        cert_table.setStyle(
            TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafafa")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        story.append(KeepTogether([cert_table]))
        story.append(Spacer(1, 14))

        # 8. Disclaimer
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8"), spaceAfter=6))
        story.append(
            Paragraph(
                "This document is generated automatically by the B-SHIELD (IBVAP) Intelligent Border Video Analytics Platform. "
                "All cryptographic signatures and evidence hashes can be verified in real time via the IBVAP Evidence API.",
                footer_style,
            )
        )

        doc.build(story)
        buffer.seek(0)
        return buffer


pdf_generator = IncidentPDFGenerator()
