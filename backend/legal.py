"""
legal.py — DMCA notice generator
"""
from datetime import datetime


def generate_dmca(
    owner_name: str,
    infringing_url: str,
    asset_filename: str = "sports media content",
    similarity: float = 0.0,
    status: str = "Copied",
    risk_score: float = 0.0,
) -> str:
    today = datetime.utcnow().strftime("%B %d, %Y")

    notice = f"""DMCA TAKEDOWN NOTICE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Date: {today}
Reference: DMCA-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TO WHOM IT MAY CONCERN,
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I, {owner_name}, am the exclusive rights holder of the copyrighted sports media
content referenced below. I write to notify you of infringing material that
appears on your platform/service.

I. IDENTIFICATION OF COPYRIGHTED WORK
──────────────────────────────────────
The copyrighted work that has been infringed is:

  Asset Name : {asset_filename}
  Owner      : {owner_name}
  Detection  : AI-powered perceptual fingerprint scan
  Status     : {status}
  Similarity : {similarity:.1f}%
  Risk Score : {risk_score:.1f}/100

II. IDENTIFICATION OF INFRINGING MATERIAL
──────────────────────────────────────────
The unauthorized content is currently located at:

  URL: {infringing_url}

This content reproduces my copyrighted work without authorisation,
constituting direct infringement under 17 U.S.C. § 501.

III. GOOD FAITH STATEMENT
──────────────────────────
I have a good faith belief that the use of my copyrighted work described above
is not authorised by the copyright owner, its agent, or applicable law.

IV. ACCURACY STATEMENT
───────────────────────
The information in this notification is accurate, and under penalty of perjury,
I am the owner, or authorised agent of the owner, of an exclusive right that
is allegedly infringed.

V. RELIEF REQUESTED
────────────────────
I respectfully request that you immediately:

  1. Remove or disable access to the infringing material.
  2. Notify the user responsible for the upload of this takedown action.
  3. Provide written confirmation of the removal within 5 business days.

VI. CONTACT INFORMATION
────────────────────────
Name          : {owner_name}
Submitted Via : Digital Asset Protection Platform
Date          : {today}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Signed electronically by: {owner_name}
Date: {today}

This notice was generated automatically by the Digital Asset Protection
for Sports Media platform in compliance with the Digital Millennium
Copyright Act (DMCA), 17 U.S.C. § 512(c)(3).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return notice
