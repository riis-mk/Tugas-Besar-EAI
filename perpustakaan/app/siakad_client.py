"""
HTTP client untuk mengambil data mahasiswa dari SIAKAD.
Perpustakaan tidak menyimpan registrasi mandiri — semua data mahasiswa
bersumber dari SIAKAD sebagai sistem otoritatif.
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

SIAKAD_REST_URL: str = os.getenv("SIAKAD_REST_URL", "http://siakad:8000")


def get_student_from_siakad(nim: str) -> dict | None:
    """Ambil data mahasiswa dari SIAKAD berdasarkan NIM.

    Returns:
        dict dengan data mahasiswa, atau None jika tidak ditemukan.
    Raises:
        requests.RequestException: jika terjadi error jaringan/HTTP selain 404.
    """
    url = f"{SIAKAD_REST_URL}/students/{nim}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("Gagal mengambil data mahasiswa %s dari SIAKAD: %s", nim, exc)
        raise
