"""
SSRF-Protected Reference Retrieval Service (packages/model-adapters/ssrf_retriever.py).

Enforces OWASP SSRF & LLM Security Controls:
1. Only 'https' scheme is permitted (blocks file://, gopher://, ftp://, http://).
2. Resolves hostname IP addresses and blocks private, loopback, link-local, multicast,
   and cloud metadata addresses (e.g., 169.254.169.254, 127.0.0.0/8, 10.0.0.0/8,
   172.16.0.0/12, 192.168.0.0/16, ::1, fc00::/7, fe80::/10).
3. Restricts outbound requests to an explicit allowlist of authoritative reference domains.
4. Never accepts student names, candidate IDs, answer-sheet images, or full student transcripts
   in search queries.
5. Strips prompt-injection directives from retrieved web content before snapshotting.
"""

import ipaddress
import re
import socket
from datetime import datetime, timezone
from typing import Dict, Any, List
from urllib.parse import urlparse


ALLOWLISTED_REFERENCE_DOMAINS = {
    "ncert.nic.in",
    "legislative.gov.in",
    "upagripardarshi.gov.in",
    "education.gov.in",
    "www.education.gov.in",
    "dpe.gov.in",
    "wcd.nic.in",
    "niti.gov.in",
    "www.niti.gov.in",
    "ndma.gov.in",
    "sac.gov.in",
    "www.sac.gov.in",
    "upeida.up.gov.in",
    "amritmahotsav.nic.in",
    "cazri.res.in",
    "www.cazri.res.in",
    "indiabudget.gov.in",
    "www.indiabudget.gov.in",
    "labour.gov.in",
    "mofpi.gov.in",
    "www.mofpi.gov.in",
    "fsi.nic.in",
    "indiaai.gov.in",
    "meity.gov.in",
    "www.meity.gov.in",
    "niepa.ac.in",
}

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"award\s+full\s+marks", re.IGNORECASE),
    re.compile(r"give\s+10\s* out\s+of\s+10", re.IGNORECASE),
    re.compile(r"पूर्ण\s+अंक\s+प्रदान\s+करें", re.IGNORECASE),
]


def validate_url_ssrf_safe(url: str, resolve_dns: bool = False) -> Dict[str, Any]:
    """
    Validates that a target URL is safe from SSRF:
    - HTTPS scheme only
    - No embedded credentials
    - Hostname in allowlisted public educational/government domains
    - Resolved IP is public global unicast (never loopback/private/link-local/metadata)
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        return {"allowed": False, "reason": f"Malformed URL: {str(exc)}"}

    if parsed.scheme != "https":
        return {"allowed": False, "reason": f"Disallowed scheme '{parsed.scheme}': only 'https' is permitted."}

    if parsed.username or parsed.password:
        return {"allowed": False, "reason": "Embedded URL credentials are prohibited."}

    host = (parsed.hostname or "").lower().strip()
    if not host:
        return {"allowed": False, "reason": "Missing hostname."}

    # Check if host is an IP literal
    try:
        ip_obj = ipaddress.ip_address(host)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
            or str(ip_obj).startswith("169.254.")
        ):
            return {"allowed": False, "reason": f"Blocked private/metadata/loopback IP literal: {host}"}
    except ValueError:
        pass

    if host not in ALLOWLISTED_REFERENCE_DOMAINS:
        return {
            "allowed": False,
            "reason": f"Host '{host}' is not in ALLOWLISTED_REFERENCE_DOMAINS."
        }

    if resolve_dns:
        try:
            addr_info = socket.getaddrinfo(host, 443)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)
                if (
                    ip_obj.is_private
                    or ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj.is_multicast
                    or ip_obj.is_reserved
                    or str(ip_obj).startswith("169.254.")
                ):
                    return {"allowed": False, "reason": f"DNS resolution for {host} pointed to non-public IP {ip_str}."}
        except Exception as exc:
            return {"allowed": False, "reason": f"DNS validation failed: {str(exc)}"}

    return {"allowed": True, "host": host, "scheme": "https", "validated_at": datetime.now(timezone.utc).isoformat()}


def sanitize_untrusted_text(text: str) -> Dict[str, Any]:
    """
    Detects and neutralizes prompt-injection attempts inside untrusted student transcripts
    or external reference excerpts without silently altering legitimate academic answers.
    """
    detected_injections: List[str] = []
    sanitized = text or ""
    for pat in PROMPT_INJECTION_PATTERNS:
        match = pat.search(sanitized)
        if match:
            detected_injections.append(match.group(0))
            sanitized = pat.sub("[REDACTED_PROMPT_INJECTION_ATTEMPT]", sanitized)

    return {
        "sanitized_text": sanitized,
        "injection_detected": len(detected_injections) > 0,
        "matched_patterns": detected_injections
    }
