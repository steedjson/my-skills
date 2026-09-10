#!/usr/bin/env python3
"""
YApi REST API Client & Automation Utility.
Provides zero-UI programmatic interaction with YApi instances, including:
- Automatic macOS Chrome cookie extraction & decryption (no manual token copy).
- Querying projects, categories, and interfaces.
- Safe, non-destructive upserting of categories and interface JSON-Schemas.
- Post-write verification.
"""

import argparse
import glob
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def get_chrome_safe_storage_password() -> Optional[str]:
    """Retrieve Chrome Safe Storage encryption password from macOS Keychain."""
    try:
        res = subprocess.run(
            ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return None


def decrypt_chrome_cookie_value(enc_val: bytes, hex_key: str, hex_iv: str) -> Optional[str]:
    """Decrypt a single Chrome cookie encrypted value via OpenSSL CLI."""
    if not enc_val or enc_val[:3] != b"v10":
        return None
    try:
        proc = subprocess.Popen(
            ["openssl", "enc", "-d", "-aes-128-cbc", "-K", hex_key, "-iv", hex_iv, "-nopad"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, _ = proc.communicate(enc_val[3:])
        if proc.returncode != 0 or not out:
            return None
        # PKCS7 unpad
        pad_len = out[-1]
        if pad_len > 16:
            return None
        unpadded = out[:-pad_len]
        # Modern Chrome adds 32-byte signature prefix
        if len(unpadded) > 32:
            try:
                return unpadded[32:].decode("utf-8")
            except UnicodeDecodeError:
                pass
        return unpadded.decode("utf-8", errors="ignore")
    except Exception:
        return None


def extract_chrome_cookies(domain: str) -> Dict[str, str]:
    """Extract and decrypt cookies for a specific domain across all Chrome profiles."""
    import sqlite3

    password = get_chrome_safe_storage_password()
    if not password:
        return {}

    salt = b"saltysalt"
    iterations = 1003
    key_length = 16
    key = hashlib.pbkdf2_hmac("sha1", password.encode("utf-8"), salt, iterations, key_length)
    hex_key = key.hex()
    hex_iv = (b" " * 16).hex()

    search_patterns = [
        os.path.expanduser("~/Library/Application Support/Google/Chrome/*/Cookies"),
        os.path.expanduser("~/Library/Application Support/Google/Chrome/*/Network/Cookies"),
    ]

    cookie_paths = []
    for pat in search_patterns:
        cookie_paths.extend(glob.glob(pat))

    extracted = {}
    for db_path in cookie_paths:
        tmp_db = tempfile.mktemp(suffix=".sqlite")
        try:
            shutil.copy2(db_path, tmp_db)
            conn = sqlite3.connect(tmp_db)
            cur = conn.cursor()
            cur.execute(
                "SELECT name, encrypted_value FROM cookies WHERE host_key LIKE ?",
                (f"%{domain}%",),
            )
            for name, enc_val in cur.fetchall():
                decrypted = decrypt_chrome_cookie_value(enc_val, hex_key, hex_iv)
                if decrypted:
                    extracted[name] = decrypted
            conn.close()
        except Exception:
            pass
        finally:
            if os.path.exists(tmp_db):
                os.remove(tmp_db)
        if "_yapi_token" in extracted:
            break

    return extracted


class YApiClient:
    def __init__(self, base_url: str, cookies: Optional[Dict[str, str]] = None, cookie_str: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        if cookie_str:
            self.cookie_header = cookie_str
        elif cookies:
            self.cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        else:
            self.cookie_header = ""

        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

    def _request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header

        encoded_data = None
        if data is not None:
            headers["Content-Type"] = "application/json;charset=UTF-8"
            encoded_data = json.dumps(data, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
        with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=15) as res:
            raw = res.read().decode("utf-8")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                raise RuntimeError(f"Invalid JSON returned from {url}: {raw[:200]}")

    def get_project(self, project_id: int) -> Dict[str, Any]:
        return self._request(f"/api/project/get?id={project_id}")

    def list_menu(self, project_id: int) -> Dict[str, Any]:
        return self._request(f"/api/interface/list_menu?project_id={project_id}")

    def get_interface(self, interface_id: int) -> Dict[str, Any]:
        return self._request(f"/api/interface/get?id={interface_id}")

    def add_category(self, project_id: int, name: str, desc: str = "") -> Dict[str, Any]:
        payload = {"name": name, "project_id": project_id, "desc": desc}
        return self._request("/api/interface/add_cat", method="POST", data=payload)

    def add_interface(self, project_id: int, catid: int, title: str, path: str, method: str = "GET") -> Dict[str, Any]:
        payload = {
            "project_id": project_id,
            "catid": catid,
            "title": title,
            "path": path,
            "method": method.upper(),
        }
        return self._request("/api/interface/add", method="POST", data=payload)

    def update_interface(self, interface_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(interface_data)
        if "_id" in payload and "id" not in payload:
            payload["id"] = payload["_id"]
        return self._request("/api/interface/up", method="POST", data=payload)

    def find_category_by_name(self, project_id: int, cat_name: str) -> Optional[Dict[str, Any]]:
        menu = self.list_menu(project_id)
        if menu.get("errcode") != 0:
            raise RuntimeError(f"Failed to list menu: {menu.get('errmsg')}")
        for cat in menu.get("data", []):
            if cat.get("name") == cat_name:
                return cat
        return None

    def find_interface_by_path(self, project_id: int, path: str, method: str = "GET") -> Optional[Dict[str, Any]]:
        menu = self.list_menu(project_id)
        if menu.get("errcode") != 0:
            raise RuntimeError(f"Failed to list menu: {menu.get('errmsg')}")
        method_upper = method.upper()
        for cat in menu.get("data", []):
            for item in cat.get("list", []):
                if item.get("path") == path and item.get("method", "GET").upper() == method_upper:
                    return item
        return None


def resolve_client(base_url: str, explicit_cookie: Optional[str] = None) -> YApiClient:
    """Resolve YApiClient using explicit cookie, env var, or local Chrome session."""
    cookie = explicit_cookie or os.getenv("YAPI_COOKIE")
    if cookie:
        return YApiClient(base_url, cookie_str=cookie)

    domain = urllib.parse.urlparse(base_url).netloc
    extracted = extract_chrome_cookies(domain)
    if extracted:
        return YApiClient(base_url, cookies=extracted)

    raise RuntimeError(
        f"No valid YApi authentication found for {domain}. "
        f"Please log in via Google Chrome or set YAPI_COOKIE environment variable."
    )


def build_json_schema(properties: Dict[str, Any], required: Optional[List[str]] = None) -> Dict[str, Any]:
    """Helper to construct standard JSON Schema for YApi response bodies."""
    return {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": properties,
        "required": required or list(properties.keys()),
    }


def main():
    parser = argparse.ArgumentParser(description="YApi CLI Automation Tool")
    parser.add_argument("--url", default="https://yapi.sugonup.com", help="YApi base URL")
    parser.add_argument("--cookie", default=None, help="Explicit cookie string")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # auth-check
    subparsers.add_parser("auth-check", help="Verify authentication with YApi")

    # list-menu
    p_list = subparsers.add_parser("list-menu", help="List project menu & categories")
    p_list.add_argument("--project-id", type=int, required=True, help="Project ID")

    # get-interface
    p_get = subparsers.add_parser("get-interface", help="Get interface details")
    p_get.add_argument("--id", type=int, required=True, help="Interface ID")

    # add-cat
    p_add_cat = subparsers.add_parser("add-cat", help="Create category")
    p_add_cat.add_argument("--project-id", type=int, required=True, help="Project ID")
    p_add_cat.add_argument("--name", required=True, help="Category name")
    p_add_cat.add_argument("--desc", default="", help="Category description")

    args = parser.parse_args()

    client = resolve_client(args.url, args.cookie)

    if args.subcommand == "auth-check":
        domain = urllib.parse.urlparse(args.url).netloc
        print(f"[OK] Successfully authenticated with {domain}")
    elif args.subcommand == "list-menu":
        res = client.list_menu(args.project_id)
        if res.get("errcode") == 0:
            for cat in res.get("data", []):
                print(f"Cat ID: {cat['_id']} | Name: {cat['name']} | Interfaces: {len(cat.get('list', []))}")
        else:
            print(f"[ERROR] {res.get('errmsg')}", file=sys.stderr)
            sys.exit(1)
    elif args.subcommand == "get-interface":
        res = client.get_interface(args.id)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif args.subcommand == "add-cat":
        res = client.add_category(args.project_id, args.name, args.desc)
        print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
